from dotenv import load_dotenv
from os import system, getenv
from subprocess import Popen, PIPE
from time import sleep

class Linphone():
    def __init__(self, default_call_address: str = None) -> None:
        self.default_call_address = default_call_address
    
    def __enter__(self):
        self.p = Popen('linphonecsh init', shell=True, stdin=PIPE)
        self.p.wait()
        print('Initiated successfully!')
        return self

    def __exit__(self, type, value, traceback):
        self.p.communicate('linphonecsh exit')
        self.p.kill()
        print('Exited correctly!')
    
    def answer_call(self):
        self.p.communicate('linphonecsh generic "answer"')
    
    def call(self, sip_address: str = None):
        call_address = self.default_call_address if sip_address == None else sip_address
        print(f'Will make a call to {call_address}!')
        self.p.communicate(f'linphonecsh generic "call {call_address}"')


load_dotenv()
MY_SIP_ADDRESS = getenv('MY_SIP_ADDRESS')
print(f'sip address: {MY_SIP_ADDRESS}')

with Linphone(MY_SIP_ADDRESS) as voip:
    # sleep(5)
    voip.call()

    a = input('Press enter to end.')