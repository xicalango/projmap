#!/usr/bin/env python2

import wx
import numpy as np

import logging

logging.basicConfig(level=logging.DEBUG)

class Transformation():
  def __init__(self, transformationMatrix, transformationMatrixReverse):
    self.transformationMatrix = transformationMatrix
    self.transformationMatrixReverse = transformationMatrixReverse

  @staticmethod
  def createTransformation(dstPoints, srcPoints = None):
    srcPoints = srcPoints or [ (0,0), (1,0), (1,1), (0,1) ]

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
    logging.debug("%s -l2s> %s", point, sp)
    return sp

  def screenToLogic(self, point):
    lp = self.__transform(point, self.transformationMatrixReverse)
    logging.debug("%s -s2l> %s", point, lp)
    return lp
    


class ProjMapWindow(wx.Window):

    MODE_CALIBRATE = 0
    MODE_DRAW = 1

    def __init__(self, parent):
        super(ProjMapWindow, self).__init__(parent, style=wx.NO_FULL_REPAINT_ON_RESIZE)
        self.mode = ProjMapWindow.MODE_CALIBRATE
        self.initDrawing()
        self.bindEvents()
        self.initBuffer()

    def initDrawing(self):
        self.SetBackgroundColour('BLACK')
        self.markers = []
        self.points = []

    def bindEvents(self):
        for event, handler in [ \
                (wx.EVT_LEFT_UP, self.onLeftUp),     # Stop drawing 
                (wx.EVT_SIZE, self.onSize),          # Prepare for redraw
                (wx.EVT_IDLE, self.onIdle),          # Redraw
                (wx.EVT_PAINT, self.onPaint),        # Refresh
                ]:
            self.Bind(event, handler)

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

    def onLeftUp(self, event):
        ''' Called when the left mouse button is released. '''
        if self.mode == ProjMapWindow.MODE_CALIBRATE:
          self.markers.append(event.GetPositionTuple())
          if len(self.markers) == 4:
            self.calibrate()
            self.points = [ (0,0), (1,0), (1,1), (0,1), (.5, .5) ]
        elif self.mode == ProjMapWindow.MODE_DRAW:
          pos = event.GetPositionTuple()
          logicPos = self.transformation.screenToLogic(pos)
          self.points.append( logicPos )

        dc = wx.BufferedDC(wx.ClientDC(self), self.buffer)
        self.redraw(dc)

    def calibrate(self):
      transformation = Transformation.createTransformation(self.markers)
      self.set_transformation(transformation)

    def set_transformation(self, transformation):
      assert self.mode == ProjMapWindow.MODE_CALIBRATE, self.mode
      self.transformation = transformation
      self.mode = ProjMapWindow.MODE_DRAW

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

    def redraw(self, dc):
      dc.BeginDrawing()
      if self.mode == ProjMapWindow.MODE_DRAW:
        pen = wx.Pen(wx.NamedColour("GREEN"), 2, wx.SOLID)
        dc.SetPen(pen)

        mapped_points = map( lambda p: self.transformation.logicToScreen(p), self.points )

        for p in mapped_points:
          dc.DrawCircle( p[0], p[1], 5 )

        for p in self.points:
          dc.DrawCircle( p[0] * 477, p[1] * 180, 5 )

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
        doodle = ProjMapWindow(self)


if __name__ == '__main__':
    app = wx.App()
    frame = ProjMapFrame()
    frame.Show()
    app.MainLoop()

