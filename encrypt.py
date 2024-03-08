# -*- coding: utf-8 -*-
#----------------------------------------------------------------------------
#v1.0
#----------------------------------------------------------------------------
'''Simple crypt module'''
from getpass import getpass
from simplecrypt import encrypt, decrypt
import wx

class Cipher(object):
    '''Class dedicated for encrypting
    and decrypting any input file with AES256 algorithm'''
    def __init__(self, p_inputFile, p_outputFile = None, p_gui = False, p_verbose = False):
        '''Constructor'''
        self.gui = p_gui
        self.inputFile = p_inputFile
        self.outputFile = p_outputFile
        self.verbose = p_verbose

    def encode(self):
        '''Encodes file'''
        if not self.outputFile:
            self.outputFile = self.inputFile + '.enc'
        with open(self.inputFile, 'rb') as content_file:
            self.inputText = content_file.read()

        if self.verbose:
            print "Encrypting %s..." % self.inputFile
        self.outputText = encrypt(self.passwd, self.inputText)


    def decode(self):
        '''Decodes file'''
        if not self.outputFile:
            self.outputFile = self.inputFile + '.dec'
        with open(self.inputFile, 'rb') as content_file:
            self.inputText = content_file.read()
        if self.verbose:
            print "Decrypting %s..." % self.inputFile
        self.outputText = decrypt(self.passwd, self.inputText)


    def saveToFile(self):
        '''Save output to file'''
        with open(self.outputFile, 'wb') as fo:
            fo.write(self.outputText)
        if self.verbose:
            print "Output file saved as %s" % self.outputFile


    def setPasswd(self):
        '''Create password protection'''
        if self.gui:
            dlg = wx.TextEntryDialog(None,"Enter Password:", "CA Cipher", style=wx.PASSWORD|wx.OK|wx.CANCEL|wx.ICON_QUESTION)
            dlg.Center()
            dlg.ShowModal()
            self.passwd = dlg.Value
            dlg.Destroy()


        else:
            self.passwd = getpass("Enter Password: ")
    @staticmethod
    def printHelp():
        '''Print help in stand alone mode'''
        print "Simple Crypt 1.0\n"
        print "Usage: encrypt.py [-edg] [Input File] [Output File]\n"
        print "Encrypts or decrypts requested file"
        print "     -e      encrypt file"
        print "     -d      decrypt file"
        print "     -g      use GUI for password prompt"       
        sys.exit(1)

if __name__ == "__main__":
    import sys, getopt
    if len(sys.argv) not in (4,5):
        Cipher.printHelp()
    else:
        opts, args = getopt.getopt(sys.argv[1:],"edg")

        opts = [i[0] for i in opts]

        encode, decode, gui = False, False, False
        for o in opts:
            if o == '-e':
                encode = True
            elif o == '-d':
                decode = True
            elif o == '-g':
                gui = True
                app = wx.App()

        if encode and decode:
            Cipher.printHelp()
        else:
            c = Cipher (args[0], args[1], gui, True)
            c.setPasswd()
            if encode:
                c.encode()
            elif decode:
                c.decode()

            c.saveToFile()

            sys.exit(0)
