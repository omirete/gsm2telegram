# Run every 15 minutes
from time import sleep
from datetime import datetime

LOG_FILE='log_sms_watchdog'
ERROR_LOG_FILE='error_log_sms_watchdog'

try:
    import utils.telegram_helpers as telegram_helpers
    import utils.sim800l_helpers as sim800l_helpers
    unread_sms = sim800l_helpers.read_sms(sim800l_helpers.SMS_STATUS.UNREAD)
    if len(unread_sms) > 0:
        telegram_helpers.send_message('You\'ve got mail!')
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f'\n{datetime.now().isoformat()}: Found {len(unread_sms)} message/s.')
        for sms in unread_sms:
            msg_for_telegram = ''
            msg_for_telegram += f'```Timestamp:   ```{sms.timestamp}\n'
            msg_for_telegram += f'```Status:      ```{sms.status}\n'
            msg_for_telegram += f'```Index:       ```{sms.index}\n'
            msg_for_telegram += f'```From:        ```{sms.sender}\n'
            msg_for_telegram += f'```SMS Content:```\n{sms.text}'
            telegram_helpers.send_message(msg_for_telegram)
        sleep(1)
    else:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f'\n{datetime.now().isoformat()}: No messages found.')
except Exception as e:
    msg_constructor = [
        'Error while checking for new sms messages.',
        '**Error message**:',
        e
    ]
    error_msg = '\n\n'.join(msg_constructor)
    with open(ERROR_LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f'\n{datetime.now().isoformat()}: Error while checking for new SMS. See detail:\n{error_msg}')
    telegram_helpers.send_message(error_msg)
    