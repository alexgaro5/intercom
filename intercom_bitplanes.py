import sounddevice as sd
import numpy as np
import struct
from intercom_buffer import Intercom_buffer
from intercom import Intercom

if __debug__:
    import sys

class Intercom_bitplanes(Intercom_buffer):

    def init(self, args):
        Intercom_buffer.init(self, args)
        #Formado Recorded_chunk, significativo, channel y bitplane. El /8 es porque compactamos el paquete a int8 y el tamaño del paquete es menor.
        self.packet_format = f"!HBB{self.frames_per_chunk//8}B"     

    def receive_and_buffer(self):
        
        #Recibimos el paquete.
        package, source_address = self.receiving_sock.recvfrom(Intercom.MAX_MESSAGE_SIZE)
        #Desempaquetamos el paquete.
        chunk_number, significant, channel, *bitplane = struct.unpack(self.packet_format, package)   
        #Pasamos el bitplane a int8.
        bitplane_int8 = np.asarray(bitplane, dtype = np.uint8)          
        #Descompactamos el bitplane.
        bitplaneunpackbits = np.unpackbits(bitplane_int8)         
        #Lo pasamos a int16.
        bitplane_int16 = bitplaneunpackbits.astype(np.int16) 
        #Guardamanos el bitplane en la posición del buffer y de channel necesario, en la posición significativa.
        self._buffer[chunk_number % self.cells_in_buffer][:,channel] |= (bitplane_int16 << significant)  
                      
        return chunk_number

    def record_send_and_play(self, indata, outdata, frames, time, status):
        
        #Recorremos el indata y vamos cogiendo columnas de mas a menos significativo.
        for significant in range(15,-1,-1):
            #Cogemos la columna con el nivel de signifido seleccionado.
            array = (indata & (1 << significant)) >> significant           
            #De las columna seleccionada, Recorremos los canales de uno en uno.
            for channel in range (0, self.number_of_channels):             
                #Cogemos el canal selecciona. 
                array_channel = array[:,channel]  
                #Lo pasamos a int8. 
                channel_int8 = array_channel.astype(np.uint8)    
                #Lo compactamos.
                channelpackbits = np.packbits(channel_int8)       
                #Lo empaquetamos en el formado especificado anteriormente.
                message = struct.pack(self.packet_format, self.recorded_chunk_number, significant, channel, *channelpackbits) 
                #Enviamos el paquete.
                self.sending_sock.sendto(message, (self.destination_IP_addr, self.destination_port))                                

        #Aumentamos el record_chunk_number.
        self.recorded_chunk_number = (self.recorded_chunk_number + 1) % self.MAX_CHUNK_NUMBER
        #Cogemos del buffer un paquete para leer.
        chunk = self._buffer[self.played_chunk_number % self.cells_in_buffer]
        #Ponemos en la posición del buffer ceros.
        self._buffer[self.played_chunk_number % self.cells_in_buffer] = self.generate_zero_chunk()
        #Aumentamos el playec_chunk_number.
        self.played_chunk_number = (self.played_chunk_number + 1) % self.cells_in_buffer

        outdata[:] = chunk
        if __debug__:
            sys.stderr.write("."); sys.stderr.flush()

    def run(self):
        self.recorded_chunk_number = 0
        self.played_chunk_number = 0

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

if __name__ == "__main__":
    intercom = Intercom_bitplanes()
    parser = intercom.add_args()
    args = parser.parse_args()
    intercom.init(args)
    intercom.run()