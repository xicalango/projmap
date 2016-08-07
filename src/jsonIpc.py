#!/usr/bin/env python2

import json
import sys
import threading
import logging

class JsonIpc(threading.Thread):
  def __init__(self, eventHandler, stdin=None, stdout=None):
    super(JsonIpc, self).__init__()
    self.eventHandler = eventHandler

    self.stdin = stdin or sys.stdin
    self.stdout = stdout or sys.stdout

  def run(self):
    self.running = True

    while self.running:
      line = self.stdin.readline()

      if len(line) == 0:
        self.running = False
        break

      try:
        jsonValue = json.loads(line)
        self.eventHandler(jsonValue, self)
      except ValueError as e:
        logging.error("coulnd't parse object: %s", e)

  def send(self, obj):
    json_value = json.dumps(obj)
    self.stdout.write(json_value)
    self.stdout.write('\n')

  def stop(self):
    self.running = False

def main():
  def print_line(json, sender):
    sender.send({"value": json})

  ipc = JsonIpc(print_line)
  ipc.start()


if __name__ == '__main__':
  main()

