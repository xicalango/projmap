#!/usr/bin/env python2

import subprocess
import json
import sys

class WxPolygon():
  def __init__(self, stdin):
    self.stdin = stdin

  def write(self, payload):
    json.dump(payload, self.stdin)
    self.stdin.write('\n')

  def setInitSize(self, w, h):
    op = {
      "op": "SetInitSize",
      "size": [w, h]
    }
    self.write(op)

  def setTransformation(self, matrix, reverseMatrix):
    op = {
      "op": "SetTransformation",
      "matrix": matrix,
      "reverseMatrix": reverseMatrix
    }
    self.write(op)

  def clearKeys(self):
    self.write({"op": "ClearRects"})

  def addKeys(self, rectangles):
    op = {
      "op": "AddRects",
      "rectangles": rectangles
    }
    self.write(op)

  def setKeys(self, rectangles):
    self.clearKeys()
    self.addKeys(rectangles)

p = subprocess.Popen(["python2", "wxPolygon.py"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)

api = WxPolygon(p.stdin)

config = {}

with open("config.json") as f:
  config = json.load(f)

api.setInitSize( config["size"][0], config["size"][1] )

api.setTransformation( config["transformation"]["matrix"], config["transformation"]["reverseMatrix"])

api.setKeys( config["keys"] )

sys.stdin.read()

p.terminate()

