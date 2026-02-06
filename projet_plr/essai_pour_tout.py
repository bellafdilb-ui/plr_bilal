import serial
import time
import serial.tools.list_ports
baud_rate = 115000
def rechercher_ports():
    global com_ports, port, ser
    ports = serial.tools.list_ports.comports()
    com_ports = [port.device for port in ports]
    if com_ports:
        port= com_ports[0]   
        print(" port=", com_ports)
        ser = serial.Serial(port, baud_rate, timeout=1, write_timeout=2)
        input_text_2= "depart\n"
        ser.write(input_text_2.encode())
rechercher_ports()

#rrr="Type : commande, Commande :depart_flash"
#ser.write(rrr.encode())
#time.sleep(2)
#rrr="Type : commande, Commande :arret_flash"
#ser.write(rrr.encode())

data =ser.readline().decode().strip() #28-01-2025
print("data=", data)
message="Type : commande, Commande :version\n" # renvoi la version du microprogramme #28-01-2025
ser.write(message.encode('utf-8'))#28-01-2025
time.sleep(1)

data =ser.readline().decode().strip() #28-01-2025
print("data=", data)

