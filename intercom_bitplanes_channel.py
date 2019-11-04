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
        self.packet_format = f"!HBB{self.frames_per_chunk//8}B"     #Formado Recorded_chunk, significativo, channel y bitplane

    def record_send_and_play_two_channel(self, indata, outdata, frames, time, status):
        
        indata[:,0] -= indata[:,1]
        #Recorremos el indata y vamos cogiendo columnas de mas a menos significativo.
        for significant in range(15,-1,-1):
            for channel in range (0, self.number_of_channels):  #De las columnas, cogemos un canal.
                array = (indata & (1 << significant)) >> significant    #Cogemos la columna.
                array_channel = array[:,channel]                        #Lo pasamos a int8.
                channel_int8 = array_channel.astype(np.uint8)           #Lo compactamos
                channelpackbits = np.packbits(channel_int8)             #Lo empaquetamos en el formado especificado anteriormente.
                message = struct.pack(self.packet_format, self.recorded_chunk_number, significant, channel, *channelpackbits)   #Enviamos el paquete.
                self.sending_sock.sendto(message, (self.destination_IP_addr, self.destination_port))

        self.recorded_chunk_number = (self.recorded_chunk_number + 1) % self.MAX_CHUNK_NUMBER
        chunk = self._buffer[self.played_chunk_number % self.cells_in_buffer]
        chunk[:,0] += chunk[:,1]
        self._buffer[self.played_chunk_number % self.cells_in_buffer] = self.generate_zero_chunk()
        self.played_chunk_number = (self.played_chunk_number + 1) % self.cells_in_buffer

        outdata[:] = chunk
        if __debug__:
            sys.stderr.write("."); sys.stderr.flush()
        
    def run(self):
        self.recorded_chunk_number = 0
        self.played_chunk_number = 0

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