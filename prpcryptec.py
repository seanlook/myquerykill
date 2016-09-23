#coding: utf8

from Crypto.Cipher import AES
from binascii import b2a_hex, a2b_hex
import base64
import sys, getopt

class prpcrypt():
    def __init__(self, key):
        #这里密钥key 长度必须为16（AES-128）、24（AES-192）、或32（AES-256）Bytes 长度.
        #目前AES-128足够用
        self.key = key
        self.mode = AES.MODE_CBC

    #加密函数，如果text不是16的倍数【加密文本text必须为16的倍数！】，那就补足为16的倍数
    def encrypt(self, text):
        cryptor = AES.new(self.key, self.mode, self.key)
        #这里密钥key 长度必须为16（AES-128）、24（AES-192）、或32（AES-256）Bytes 长度.目前AES-128足够用
        length = 16
        count = len(text)
        add = length - (count % length)
        text = text + ('\0' * add)
        self.ciphertext = cryptor.encrypt(text)
        #print self.ciphertext
        #因为AES加密时候得到的字符串不一定是ascii字符集的，输出到终端或者保存时候可能存在问题
        #所以这里统一把加密后的字符串转化为16进制字符串
        #return b2a_hex(self.ciphertext)
        return  base64.b64encode(self.ciphertext)

    #解密后，去掉补足的空格用strip() 去掉
    def decrypt(self, text):
        cryptor = AES.new(self.key, self.mode, self.key)
        #plain_text = cryptor.decrypt(a2b_hex(text))
        plain_text = cryptor.decrypt(base64.b64decode(text))
        return plain_text.rstrip('\0')

def usage():
    print """
    Usage: prpcryptec.py -k <keystring> [-d|-e] <text>
        -k , --key=  :  your decrypt/encrypt key string. MUST be given and 16 length
        -d  :  decrypt your cipher_text given
        -e  :  encrypt your plain_text given
               either -d or -e MUST be given
        -h, --help  :  print this help
    """

if __name__ == '__main__':
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hd:e:k:", ['key=', 'help'])
    except getopt.GetoptError as err:
        print 'Error: ', err
        print 'Use -h to get usage'
        sys.exit(2)


    key = ""
    crypt_str = ""
    crypt_type = 0
    for o, a in opts:
        if o in ("-h", "--help"):
            usage()
            sys.exit(1)
        elif o in ("-k", "--key"):
            if len(a) ==16:
                key = a
            else:
                print "Error: key must be 16 bytes long"
                sys.exit(2)
        elif o in ("-d"):
            crypt_str = a
            crypt_type = 0
            print ">> Decrypt the string: %s" % a
        elif o in ("-e"):
            crypt_str = a
            crypt_type = 1
            print ">> Encrypt the string: %s" % a

    if crypt_str == "":
        print "Error: either -d or -e MUST be given"
        sys.exit(2)

    try:
        pc = prpcrypt(key)
        if crypt_type == 0:
            print pc.decrypt(crypt_str)
        else:
            print pc.encrypt(crypt_str)
        print ""
    except:
        print "Error: Incorrect option or value givien"
        usage()

