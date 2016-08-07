#!/usr/bin/env python2

import wx
import numpy as np

import logging

import jsonIpc

logging.basicConfig(level=logging.DEBUG)

EVT_IPC_ID = wx.NewId()

def EVT_IPC(win, func):
  win.Connect(-1, -1, EVT_IPC_ID, func)

class IpcEvent(wx.PyEvent):
  def __init__(self, data, sender):
    #super(wx.PyEvent, self).__init__()
    wx.PyEvent.__init__(self)
    self.SetEventType(EVT_IPC_ID)
    self.data = data
    self.sender = sender

class Transformation():
  def __init__(self, transformationMatrix, transformationMatrixReverse):
    self.transformationMatrix = transformationMatrix
    self.transformationMatrixReverse = transformationMatrixReverse

  @staticmethod
  def createTransformation(dstPoints, srcPoints = None):
    srcPoints = srcPoints or [ (0,0), (23.7,0), (23.7,9), (0,9) ]

    dstMatrix = Transformation.calcMatrix( dstPoints )
    dstMatrixInv = np.linalg.inv(dstMatrix)

    srcMatrix = Transformation.calcMatrix( srcPoints )
    srcMatrixInv = np.linalg.inv(srcMatrix)

    transformationMatrix = np.matmul(dstMatrix, srcMatrixInv)
    transformationMatrixReverse = np.matmul(srcMatrix, dstMatrixInv)

    return Transformation(transformationMatrix, transformationMatrixReverse)

  @staticmethod
  def calcMatrix(points):
    a = np.array( [ [points[0][0], points[1][0], points[2][0]] 
                  , [points[0][1], points[1][1], points[2][1]]
                  , [1, 1, 1]
                  ] )
    b = np.array( [points[3][0], points[3][1], 1] )

    x = np.linalg.solve(a, b)

    return a * x

  def __transform(self, point, matrix):
    ph = np.array( [point[0], point[1], 1] )
    tph = np.matmul(matrix, ph)

    return (tph[0] / tph[2], tph[1] / tph[2])
    

  def logicToScreen(self, point):
    sp = self.__transform(point, self.transformationMatrix)
    return sp

  def screenToLogic(self, point):
    lp = self.__transform(point, self.transformationMatrixReverse)
    return lp
    

class Rectangle():
  def __init__(self, posx, posy, sizex, sizey):
    self.posx = posx
    self.posy = posy
    self.sizex = sizex
    self.sizey = sizey

  def get_points(self):
    return [
      (self.posx, self.posy),
      (self.posx + self.sizex, self.posy),
      (self.posx + self.sizex, self.posy + self.sizey),
      (self.posx, self.posy + self.sizey)
    ]

class RectangleShape():
  def __init__(self, rect, color = "white"):
    self.rect = rect
    self.set_color(color)

  def set_color(self, color):
    self.pen = wx.Pen(wx.NamedColour(color), 1, wx.SOLID)
    self.brush = wx.Brush(wx.NamedColour(color))

  def draw(self, dc, transformation):
    points = map( lambda p: wx.Point(int(p[0]), int(p[1])), map( lambda p: transformation.logicToScreen(p), self.rect.get_points() ))

    oldPen = dc.GetPen()
    oldBrush = dc.GetBrush()

    dc.SetPen( self.pen )
    dc.SetBrush( self.brush )

    dc.DrawPolygon( points )

    unmapped_points = map( lambda p: wx.Point(int(p[0]*10), int(p[1]*10)), self.rect.get_points() )

    dc.DrawPolygon( unmapped_points )

    dc.SetPen( oldPen )
    dc.SetBrush( oldBrush )
    

class ProjMapWindow(wx.Window):

    MODE_CALIBRATE = 0
    MODE_DRAW = 1

    def __init__(self, parent):
        super(ProjMapWindow, self).__init__(parent, style=wx.NO_FULL_REPAINT_ON_RESIZE)
        self.mode = ProjMapWindow.MODE_CALIBRATE
        self.clearScreen = True
        self.initSize = None
        self.initDrawing()
        self.bindEvents()
        self.initBuffer()

    def initDrawing(self):
        self.SetBackgroundColour('WHITE')
        self.markers = []
        self.rects = []

    def bindEvents(self):
        for event, handler in [ \
                (wx.EVT_LEFT_UP, self.onLeftUp),     # Stop drawing 
                (wx.EVT_SIZE, self.onSize),          # Prepare for redraw
                (wx.EVT_IDLE, self.onIdle),          # Redraw
                (wx.EVT_PAINT, self.onPaint),        # Refresh
                (wx.EVT_KEY_DOWN, self.onChar),
                ]:
            self.Bind(event, handler)

        EVT_IPC(self, self.onIpc)

    def initBuffer(self):
        ''' Initialize the bitmap used for buffering the display. '''
        size = self.GetClientSize()
        self.buffer = wx.EmptyBitmap(size.width, size.height)
        dc = wx.BufferedDC(None, self.buffer)
        dc.SetBackground(wx.Brush(self.GetBackgroundColour()))
        dc.Clear()
        self.redraw(dc)
        self.reInitBuffer = False

    # Event handlers:

    def onIpc(self, event):
      data = event.data
      op = data["op"]

      logging.debug("ipc: %s", data)

      if op == "SetInitSize":
        size = data["size"]
        self.set_init_size( size[:2] )
      elif op == "Quit":
        self.Close()
      elif op == "GetTransformation":
        self.ipc_get_transformation()
      elif op == "SetTransformation":
        self.ipc_set_transformation(data)
      elif op == "GetRects":
        self.ipc_get_rects()
      elif op == "AddRect":
        self.ipc_add_rect(data)
      elif op == "AddRects":
        self.ipc_add_rects(data)
      elif op == "ClearRects":
        self.ipc_clear_rects()
      elif op == "SetMode":
        self.ipc_set_mode(data)
      elif op == "SetRectColor":
        self.ipc_set_rect_color(data)
      else:
        logging.error("unknown op: %s", op)

    def ipc_set_rect_color(self, data):
      rect_id = data["id"]
      rect = self.rects[rect_id]
      rect.set_color(data["color"])
      self.redraw()

    def ipc_set_mode(self, data):
      if data["mode"] == "calibrate":
        self.set_mode(ProjMapWindow.MODE_CALIBRATE)
      elif data["mode"] == "draw":
        self.set_mode(ProjMapWindow.MODE_DRAW)

    def ipc_clear_rects(self):
      self.rects = []
      self.clearScreen = True
      self.redraw()

    def ipc_add_rect(self, data):
      rect_data = data["rectangle"]
      rect = Rectangle( rect_data[0], rect_data[1], rect_data[2], rect_data[3] )
      rect_shape = RectangleShape(rect)
      self.rects.append(rect_shape)
      self.redraw()

    def ipc_add_rects(self, data):
      rect_data = data["rectangles"]
      for rect in rect_data:
        new_rect = Rectangle( rect[0], rect[1], rect[2], rect[3] )
        rect_shape = RectangleShape(new_rect)
        self.rects.append(rect_shape)

      self.redraw()

    def ipc_get_rects(self):
      rects = list( map( lambda r: [ r.rect.posx, r.rect.posy, r.rect.sizex, r.rect.sizey ], self.rects ) )
      self.ipc.send(rects)

    def ipc_get_transformation(self):
      transformation = {
        "matrix": self.transformation.transformationMatrix.tolist(),
        "reverseMatrix": self.transformation.transformationMatrixReverse.tolist()
      }
      self.ipc.send(transformation)

    def ipc_set_transformation(self, data):
      self.set_mode(ProjMapWindow.MODE_CALIBRATE)
      transformation = Transformation(data["matrix"], data["reverseMatrix"])
      self.set_transformation(transformation)

    def onChar(self, event):
      pass

    def onLeftUp(self, event):
        ''' Called when the left mouse button is released. '''

        logging.debug("mode: %d", self.mode)

        if self.mode == ProjMapWindow.MODE_CALIBRATE:
          self.add_marker(event.GetPositionTuple())
        elif self.mode == ProjMapWindow.MODE_DRAW:
          pos = event.GetPositionTuple()
          logicPos = self.transformation.screenToLogic(pos)
          rect = Rectangle(logicPos[0], logicPos[1], 1.2, 1.2)
          rectShape = RectangleShape(rect)
          self.rects.append(rectShape)

        self.redraw()


    def add_marker(self, marker):
      if len(self.markers) < 4:
        self.markers.append(marker)
        logging.debug("markers: %d", len(self.markers))
        self.calibrate_when_ready()

    def calibrate_when_ready(self):
      if len(self.markers) == 4 and self.initSize != None:
        self.calibrate()

    def set_init_size(self, size):
      logging.debug("setting init size to %s", size)
      self.initSize = size
      self.calibrate_when_ready()

    def calibrate(self):
      srcPoints = [ (0,0), (self.initSize[0], 0), (self.initSize[0], self.initSize[1]), (0, self.initSize[1]) ]
      transformation = Transformation.createTransformation(self.markers, srcPoints)
      self.set_transformation(transformation)

    def set_transformation(self, transformation):
      assert self.mode == ProjMapWindow.MODE_CALIBRATE, self.mode
      self.transformation = transformation
      self.set_mode(ProjMapWindow.MODE_DRAW)

    def set_mode(self, mode):
      if self.mode == mode:
        return

      self.mode = mode

      self.clearScreen = True
      if mode == ProjMapWindow.MODE_CALIBRATE:
        self.markers = []
        self.SetBackgroundColour("WHITE")
      elif mode == ProjMapWindow.MODE_DRAW:
        self.SetBackgroundColour("BLACK")

      self.redraw()

    def onSize(self, event):
        ''' Called when the window is resized. We set a flag so the idle
            handler will resize the buffer. '''
        self.reInitBuffer = True

    def onIdle(self, event):
        ''' If the size was changed then resize the bitmap used for double
            buffering to match the window size.  We do it in Idle time so
            there is only one refresh after resizing is done, not lots while
            it is happening. '''
        if self.reInitBuffer:
            self.initBuffer()
            self.Refresh(False)

    def onPaint(self, event):
        ''' Called when the window is exposed. '''
        # Create a buffered paint DC.  It will create the real
        # wx.PaintDC and then blit the bitmap to it when dc is
        # deleted.  Since we don't need to draw anything else
        # here that's all there is to it.
        dc = wx.BufferedPaintDC(self, self.buffer)


    def redraw(self, dc = None):
      dc = dc or wx.BufferedDC(wx.ClientDC(self), self.buffer)
      dc.BeginDrawing()

      if self.clearScreen:
        dc.Clear()
        self.clearScreen = False

      if self.mode == ProjMapWindow.MODE_DRAW:
        for rect in self.rects:
          rect.draw(dc, self.transformation)

      elif self.mode == ProjMapWindow.MODE_CALIBRATE:
        pen = wx.Pen(wx.NamedColour("RED"), 2, wx.SOLID)
        dc.SetPen(pen)
        for m in self.markers:
          dc.DrawCircle( m[0], m[1], 5 )
      dc.EndDrawing()

class ProjMapFrame(wx.Frame):
    def __init__(self, parent=None):
        super(ProjMapFrame, self).__init__(parent, title="Doodle Frame", 
            size=(800,600), 
            style=wx.DEFAULT_FRAME_STYLE|wx.NO_FULL_REPAINT_ON_RESIZE)
        self.window = ProjMapWindow(self)


if __name__ == '__main__':
    app = wx.App()
    frame = ProjMapFrame()
    frame.ShowFullScreen(True)
    wx.SetCursor(wx.StockCursor(wx.CURSOR_CROSS))

    def ipc_event_handler(event, sender):
      wx.PostEvent(frame.window, IpcEvent(event, sender))
    
    ipc = jsonIpc.JsonIpc( ipc_event_handler )
    ipc.start()

    frame.window.ipc = ipc

    app.MainLoop()

