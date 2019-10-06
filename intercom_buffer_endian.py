import sounddevice as sd                                                        # https://python-sounddevice.readthedocs.io
import numpy                                                                    # https://numpy.org/
import socket                                                                   # https://docs.python.org/3/library/socket.html
import sys
from intercom import Intercom
import struct

class IntercomBuffer(Intercom):

    def init(self, args):
        Intercom.init(self, args)
        self.chunk_to_play = 0

    def run(self):
        sending_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        receiving_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        listening_endpoint = ("0.0.0.0", self.listening_port)
        receiving_sock.bind(listening_endpoint)

        lista = [numpy.zeros((self.samples_per_chunk, self.number_of_channels), self.dtype)]*self.buffer_capacity

        def receive_and_buffer():
            array, source_address = receiving_sock.recvfrom(self.max_packet_size)

            array = struct.unpack('<H{}h'.format(self.samples_per_chunk * self.number_of_channels),array)

            pos = int(array[0]) % self.buffer_capacity
            array = numpy.delete(array, 0)
        
            lista[pos] = array
        
        def record_send_and_play (indata, outdata, frames, time, status):
            array = numpy.frombuffer(indata, dtype=self.dtype)
            
            array = numpy.insert(array, 0, self.chunk_to_play)
            array = struct.pack('<H{}h'.format(self.samples_per_chunk * self.number_of_channels), *array)
            
            message = lista[self.chunk_to_play % self.buffer_capacity]                                          
            lista[self.chunk_to_play % self.buffer_capacity] = numpy.zeros((self.samples_per_chunk, self.number_of_channels), dtype=self.dtype)
            self.chunk_to_play = (self.chunk_to_play + 1) % self.buffer_capacity

            sending_sock.sendto(array, (self.destination_IP_addr, self.destination_port))

            outdata[:] = numpy.reshape(message, (self.samples_per_chunk, self.number_of_channels))

            sys.stderr.write("."); sys.stderr.flush()

        with sd.Stream(
                samplerate=self.samples_per_second,
                blocksize=self.samples_per_chunk,
                dtype=self.dtype,
                channels=self.number_of_channels,
                callback=record_send_and_play):
            while True:
                receive_and_buffer()

if __name__ == "__main__":
    intercom = IntercomBuffer()
    parser = intercom.add_args()
    args = parser.parse_args()
    intercom.init(args)
    intercom.run()