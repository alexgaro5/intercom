import sounddevice as sd
import numpy as np
import struct
from intercom_bitplanes import Intercom_bitplanes
from intercom_buffer import Intercom_buffer
from intercom import Intercom

if __debug__:
    import sys

class Intercom_bitplanes_nuevo(Intercom_bitplanes):

    def init(self, args):
        Intercom_bitplanes.init(self, args)
        self.packet_format = f"!HBB{self.frames_per_chunk//8}B"     

    #Vamos a crear un nuevo metodo que solo va a funcionar si hay dos canales, pues es donde vamos a hacer lo de restar un canal y luego sumarlo. Si hay solo un canal, se utilizará el método de intercom_bitplane.py, que no hace nada de restar y luego sumar los canales.
    def record_send_and_play_two_channel(self, indata, outdata, frames, time, status):
        
        indata[:,0] -= indata[:,1]                                                                                              #Le restamos el canal 1 al 0 antes de empezar a enviarlos.
        
        for significant in range(15,-1,-1):
            array = (indata & (1 << significant)) >> significant   
            for channel in range (0, self.number_of_channels):      
                array_channel = array[:,channel]                        
                channel_int8 = array_channel.astype(np.uint8)           
                channelpackbits = np.packbits(channel_int8)             
                message = struct.pack(self.packet_format, self.recorded_chunk_number, significant, channel, *channelpackbits)   
                self.sending_sock.sendto(message, (self.destination_IP_addr, self.destination_port))

        self.recorded_chunk_number = (self.recorded_chunk_number + 1) % self.MAX_CHUNK_NUMBER
        chunk = self._buffer[self.played_chunk_number % self.cells_in_buffer]
        chunk[:,0] += chunk[:,1]                                                                                               #Le sumamos el canal 1 al 0 una vez recibido, antes de empezar a reproducirlo.
        self._buffer[self.played_chunk_number % self.cells_in_buffer] = self.generate_zero_chunk()
        self.played_chunk_number = (self.played_chunk_number + 1) % self.cells_in_buffer

        outdata[:] = chunk
        if __debug__:
            sys.stderr.write("."); sys.stderr.flush()
        
    def run(self):
        self.recorded_chunk_number = 0
        self.played_chunk_number = 0

        #Si  el numero de canales es 1, se llama al metodo de record_send_and_play de intercom_bitplane.py sin hacer nada con los canales. Ya que solo existe un canal y no podemos restar/sumar uno con otro.
        if self.number_of_channels == 1:   

            with sd.Stream(samplerate=self.frames_per_second, 
                            blocksize=self.frames_per_chunk, 
                            dtype=np.int16, 
                            channels=self.number_of_channels, 
                            callback=self.record_send_and_play):
                print("-=- Press CTRL + c to quit -=-")
                first_received_chunk_number = self.receive_and_buffer()
                self.played_chunk_number = (first_received_chunk_number - self.chunks_to_buffer) % self.cells_in_buffer
                while True:
                    self.receive_and_buffer()
        #Si  el numero de canales es 2, se llama al metodo de record_send_and_play de esta clase, sumando/restando el canal 1 al 0 para enviar y recibir. Si queremos probar este método nuevo, deberemos de ejecutar el código con dos canales, si no utilizaremos el códiogo del issue anterior. Esto se hace para permitir que el código siga siendo compatible con 1 y 2 canales.
        else:

            with sd.Stream(samplerate=self.frames_per_second, 
                            blocksize=self.frames_per_chunk, 
                            dtype=np.int16, 
                            channels=self.number_of_channels, 
                            callback=self.record_send_and_play_two_channel):
                print("-=- Press CTRL + c to quit -=-")
                first_received_chunk_number = self.receive_and_buffer()
                self.played_chunk_number = (first_received_chunk_number - self.chunks_to_buffer) % self.cells_in_buffer
                while True:
                    self.receive_and_buffer()

if __name__ == "__main__":
    intercom = Intercom_bitplanes_nuevo()
    parser = intercom.add_args()
    args = parser.parse_args()
    intercom.init(args)
    intercom.run()