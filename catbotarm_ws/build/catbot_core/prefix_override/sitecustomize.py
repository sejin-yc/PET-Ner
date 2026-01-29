import sys
if sys.prefix == '/usr':
    sys.real_prefix = sys.prefix
    sys.prefix = sys.exec_prefix = '/home/ssafy/roboticarm/S14P11C203/catbotarm_ws/install/catbot_core'
