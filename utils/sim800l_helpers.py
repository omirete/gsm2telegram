import serial, re
import RPi.GPIO as GPIO
from time import sleep, time
from dotenv import load_dotenv
from os import getenv

load_dotenv()

SERIAL_PORT = getenv("SERIAL_PORT")
SERIAL_BAUD = 9600
SERIAL_TIMEOUT = 5
GSM_TIMEOUT = 5
PAUSE_AFTER_SERIAL_OPEN = 2
PAUSE_BEFORE_SERIAL_READ = .05
CODEC_LIST = ['utf-8', 'latin-1', 'utf-16-be']

GPIO.setmode(GPIO.BCM)
RST_PIN = 17
# GPIO.setmode(GPIO.BOARD)
# RST_PIN = 11

GPIO.setup(RST_PIN, GPIO.OUT) # RST pin
GPIO.output(RST_PIN, 1)       # Normally high.

class SMS_STATUS:
    ALL = "ALL"
    READ = "REC READ"       # Received read.
    UNREAD = "REC UNREAD"   # Received unread.
    SENT = "STO SENT"       # Stored sent.
    UNSENT = "STO UNSENT"   # Stored unsent.

class AT_COMMAND_OUTPUT:
    def __init__(self) -> None:
        self.status = None
        self._lines = []
    
    def setStatus(self, newStatus: str):
        self.status = newStatus
    
    def addLine(self, newLine: str):
        self._lines.append(newLine)

    def text(self):
        return '\n'.join(self._lines)

class SMS_Data():
    def __init__(self, text: str = None, sender: str = None, timestamp: str = None, index: int = None, status: SMS_STATUS = None) -> None:
        self.text = text
        self.sender = sender
        self.timestamp = timestamp
        self.index = index
        self.status = status

class GSMInitializationError(Exception):
    pass

class GSMTimeoutError(Exception):
    pass

class GSMCommandError(Exception):
    pass

def _write_to_serial(ser: serial.Serial, command: str):
    ser.write(command.encode('utf-8'))

def open_serial_terminal():
    print('Will open serial port...')
    with serial.Serial(SERIAL_PORT, baudrate=SERIAL_BAUD, timeout=SERIAL_TIMEOUT) as piSerial:
        print('Serial port was opened! Doing initial handshake with module...')
        sleep(PAUSE_AFTER_SERIAL_OPEN)
        __serial_initialize(piSerial, verbose=True) # Will raise GSMInitializationError if not successful
        cmd = input('Insert command (or press enter to quit): ')
        while cmd != '':
            _write_to_serial(piSerial, f'{cmd}\r\n')
            sleep(PAUSE_BEFORE_SERIAL_READ)
            line_constructor = ''
            while True:
                serial_bytes = piSerial.readline()
                flag_decoding_successful = False
                for codec in CODEC_LIST:
                    try:
                        serial_str = serial_bytes.decode(codec)
                        flag_decoding_successful = True
                        break
                    except UnicodeDecodeError as e:
                        pass
                    
                if flag_decoding_successful != True:
                    print('Could not decode bytes from serial. Bytes received:')
                    print(serial_bytes)
                    print(f'----------\n{e}\n----------')
                else:
                    if serial_str.endswith('\r\n'):
                        line_constructor += serial_str[:-2]
                        line = line_constructor
                        line_constructor = ''
                        print(line)
                        if serial_str == 'OK\r\n':
                            break
                        if serial_str == 'ERROR\r\n':
                            break
                    else:
                        line_constructor += serial_str
                        print('Still constructing output, waiting for \\r\\n chars...')
                sleep(PAUSE_BEFORE_SERIAL_READ)

            cmd = input('Insert command (or press enter to quit): ')

def reset_module():
    confirm = input('Do you really want to reset the GSM Module? (y/n): ')
    if confirm.lower() == 'y':
        GPIO.output(RST_PIN, 0)
        sleep(.15)
        GPIO.output(RST_PIN, 1)
        sleep(.8)
        print('Sent pulse for resetting module!')

def send_command(cmd: str, verbose: bool = False, serial_port: serial.Serial = None) -> AT_COMMAND_OUTPUT:

    if not cmd.endswith('\r\n'):
        cmd += '\r\n'
    
    with serial.Serial(SERIAL_PORT, baudrate=SERIAL_BAUD, timeout=SERIAL_TIMEOUT) as piSerial:
        sleep(PAUSE_AFTER_SERIAL_OPEN)
        __serial_initialize(piSerial) # Will only proceed if initialization is successful. Otherswise it raises an error.
        
        _write_to_serial(piSerial, cmd)

        output = AT_COMMAND_OUTPUT()
        line_constructor = ''

        sleep(PAUSE_BEFORE_SERIAL_READ)
        while True:
            serial_bytes = piSerial.readline()
            flag_decoding_successful = False
            for codec in CODEC_LIST:
                try:
                    serial_str = serial_bytes.decode(codec)
                    flag_decoding_successful = True
                    break
                except UnicodeDecodeError as e:
                    pass
                
            if flag_decoding_successful != True:
                if verbose == True:
                    print('Could not decode bytes from serial. Bytes received:')
                    print(serial_bytes)
                    print(f'----------\n{e}\n----------')
            else:
                if serial_str.endswith('\r\n'):
                    line_constructor += serial_str[:-2]
                    line = line_constructor
                    line_constructor = ''
                    output.addLine(line)
                    if serial_str == 'OK\r\n':
                        output.setStatus('OK')
                        break
                    if serial_str == 'ERROR\r\n':
                        output.setStatus('ERROR')
                        break
                else:
                    if verbose == True:
                        print('Still constructing output, waiting for \\r\\n chars...')
                    line_constructor += serial_str
            sleep(PAUSE_BEFORE_SERIAL_READ)
        return output

def read_sms(filter_by_status: SMS_STATUS = SMS_STATUS.UNREAD, flag_text_mode: bool = True, verbose: bool = False): # -> list[SMS_Data]:
    cmd = f'AT+CMGF={1 if flag_text_mode == True else 0}'
    if verbose == True:
        print(f'Setting mode with {cmd}...')
    output = send_command(cmd)
    if output.status == 'OK':
        if verbose == True:
            print('Finished configuring AT+CMGF!')
            print('Retrieving messages...')
        output = send_command(f'AT+CMGL="{filter_by_status}"')
        if verbose == True:
            print('Finished retrieving messages! Now parsing...')
        messages = __parse_sms(output._lines, verbose=verbose)
        if verbose == True:
            print('Finished parsing messages! See results:')
            print(f'Found {len(messages)} message/s.')
            if len(messages) > 0:
                for i in range(len(messages)):
                    msg = messages[i]
                    print('----------------------------------------------------')
                    print(f'Timestamp:   {msg.timestamp}')
                    print(f'Status:      {msg.status}')
                    print(f'Index:       {msg.index}')
                    print(f'From:        {msg.sender}')
                    print(f'SMS Content:\n{msg.text}')
                print('----------------------------------------------------')
                print('Finished printing messages.\n')
            else:
                print('No messages found.')
        return messages
    else:
        if verbose == True:
            print('Error while setting the SMS mode. See answer from GSM module:')
            print(output.text())
        raise GSMCommandError

# def __parse_sms(serial_lines: list[str], verbose: bool = False) -> list[SMS_Data]:
def __parse_sms(serial_lines: list, verbose: bool = False):
    # list_of_sms: list[SMS_Data] = []
    list_of_sms = []
    sms = None
    for i in range(len(serial_lines)):
        line = serial_lines[i]
        if line.startswith('+CMGL: '):
            if sms != None:
                list_of_sms.append(sms)
                sms = None

            line_split_by_comma = line.split(',')
            
            index = line_split_by_comma[0].split(' ')[1]
            status = line_split_by_comma[1].replace('"', '')
            sender = line_split_by_comma[2].replace('"', '')
            timestamp = f'{line_split_by_comma[-2]}T{line_split_by_comma[-1]}'
            timestamp = timestamp.replace('/', '-').replace('"', '')
            
            sms = SMS_Data(
                text='',
                sender=sender,
                timestamp=timestamp,
                index=index,
                status=status
            )

        else:
            if line != 'OK' and line != 'ERROR':
                if sms == None and line != None:
                    if verbose == True:
                        print('Unhandled line found. See line below:')
                        print(line)
                else:
                    sms.text += line
    if sms != None:
        list_of_sms.append(sms)

    if len(list_of_sms) > 0:
        hex_pattern_str = r'^(?P<content>([0-9A-F]{2})+)(\r\n)?$'
        hex_pattern = re.compile(hex_pattern_str)
        for sms in list_of_sms:
            matches = hex_pattern.search(sms.text)
            try:
                is_hex = matches.groupdict()['content'] != None
            except AttributeError:
                is_hex = False
            
            if is_hex == True:
                try:
                    sms.text = bytes.fromhex(sms.text).decode('utf-16-be')
                except UnicodeDecodeError:
                    # We tried to decode the sms, but we couldn't. In this case,
                    # we just leave the original text received and let the user
                    # decide what they want to do
                    pass
    return list_of_sms

def __serial_initialize(serial_interface: serial.Serial, verbose: bool = False):
    _write_to_serial(serial_interface, 'AT\r\n')
    if verbose == True:
        print('Sent command for initial handshake with module! Awaiting reply...')
    sleep(PAUSE_BEFORE_SERIAL_READ)
    time_start = time()
    while True:
        serial_bytes = serial_interface.readline()
        flag_decoding_successful = False
        for codec in CODEC_LIST:
            try:
                line = serial_bytes.decode(codec)
                flag_decoding_successful = True
                break
            except UnicodeDecodeError as e:
                pass
            
        if flag_decoding_successful != True:
            print('Could not decode bytes from serial. Bytes received:')
            print(serial_bytes)
            print(f'----------\n{e}\n----------')
        else:
            if line == 'OK\r\n':
                if verbose == True:
                    print('Correctly initialized communication with GSM module!')
                return True
            elif line == 'ERROR\r\n':
                raise GSMInitializationError
            elif time()-time_start > GSM_TIMEOUT:
                raise GSMTimeoutError
        sleep(PAUSE_BEFORE_SERIAL_READ)
    
def answer_call():
    send_command("ATA")