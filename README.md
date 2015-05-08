Console firmware bootloader for PIC16 microcontrollers compatible with tinybldWin (http://www.etc.ugal.ro/cchiculita/software/picbootloader.htm).

Based on tinybldLin http://tinybldlin.sourceforge.net

Tested on PIC16F only.

Requirements:
- python 2.7
- pyserial (http://pyserial.sourceforge.net/)
- pyyaml (http://pyyaml.org/)

Features:
- Supports specifying parameters via configuration file in YAML format
- Varios options to reset device (sending special sequence or HW reset using DTR line of specified serial port)

