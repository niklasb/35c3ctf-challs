from win32con import *
from win32api import *
from win32ui import *
import win32ui
from win32gui import GetClassName
from win32event import *
from time import time, ctime, sleep
import sys, os

# Captions (titles) of popup windows to confirm
# EDIT THIS
PopupNames = [
#  'Error',
#  'Information',
#  'Install Dialler', # You better delete this line :-)
]

def GetWindowText( Window ):
  """
  Get text of all 'Static' elements of windows and return
concatenated.
  """
  Child, Text = None, ''
  while 1:
    try: Child = FindWindowEx( Window, Child, 'Static', None )
    except: break
    Text += '\n\t'.join( Child.GetWindowText().split( '\r' ) )
  return Text

def FindControl( Window, CName = 'OK', CType = 'Button' ):
  """
  Find control with name CName in Window
  
  @arg Window: Top level window
  @type Window: PyCWnd
  @arg CName: Control Name
  @type CName: string
  @arg CType: Control class
  @type CType: string
  @return Control
  @rtype: PyCwnd 
  """
  return FindWindowEx( Window, None, CType, CName )


def ConfirmDialog( Window, BName = None, Delay = 0.5 ):
  """
  Find button with name BName in Window and simulate a button
activation.
  
  @arg WName: Window Name
  @type WName: string
  @arg BName: Button Name
  @type BName: string
  @return: Button in case of success, negative error code else
  @rtype: PyCWnd
  """
  # Find Button
  Button = FindControl( Window, BName )  
  Button.SendMessage( BM_SETSTATE,  1, 0 )
  sleep( Delay )  # Window should show up at least for half a second.

  # Simulate button press to confirm window
  idButton = Button.GetDlgCtrlID()
  hButton = Button.GetSafeHwnd()
  Caption = Window.GetWindowText()
  Window.SendMessage( WM_COMMAND, MAKELONG( idButton, BN_CLICKED ), hButton )

  #print ctime( time() ), "Confirmed '%s'" %Caption
  return Button

def find():
  try:
    return FindWindow( None, "pwndb.exe - Application Error")
  except win32ui.error:
    return None

if __name__ == '__main__':
  last_clean = time()
  while True:
    if time() > last_clean + 5*60:
      print 'killing processes...'
      os.system('taskkill /F /IM pwndb.exe /t')
      last_clean = time()
    sleep(1)
    print 'checking...'
    while True:
      w = find()
      if not w:
        break
      print "Closing"
      try:
        ConfirmDialog(w, "OK", 0)
      except:
        pass
      sleep(0.5)