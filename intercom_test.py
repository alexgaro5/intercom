import sounddevice as sd                                                        # https://python-sounddevice.readthedocs.io
import numpy                                                                    # https://numpy.org/
import socket                                                                   # https://docs.python.org/3/library/socket.html
import sys
import struct
from intercom import Intercom                                                   #Importing the original Intercom

class IntercomBuffer(Intercom):

    #Redifining the init method
    def init(self, args):
        Intercom.init(self, args)
        self.buffer_capacity = args.buffer_capacity
        self.chunk_to_play = 0                                                  #This is the chunk we are going to play
        self.pos = 0
        self.chunk_counter = 0
        self.delay = self.buffer_capacity // 2                                  #This is the delay we are using before playing the chunks

    def run(self):
        sending_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        receiving_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        listening_endpoint = ("0.0.0.0", self.listening_port)
        receiving_sock.bind(listening_endpoint)

        lista = [numpy.zeros((self.samples_per_chunk, self.number_of_channels), self.dtype)]*self.buffer_capacity    #Defining the structure of the buffer filled with 0

        def receive_and_buffer():
            package, source_address = receiving_sock.recvfrom(self.max_packet_size)                                 #We recieve the message via UDP

            self.pos, *message = struct.unpack('<H{}h'.format(self.samples_per_chunk * self.number_of_channels), package)  #Unpacking the message recieved 
            lista[self.pos % self.buffer_capacity] = message                                                 #Inserting the data audio in the buffer with the delay
        
        def record_send_and_play (indata, outdata, frames, time, status):
            array = numpy.frombuffer(indata, dtype=self.dtype)                                                      #Inserting indata into numpy array with the specified type
            
            package = struct.pack('<H{}h'.format(self.samples_per_chunk * self.number_of_channels), self.chunk_counter, *array)  #Packing the message to send
            
            message = lista[(self.pos + self.delay) % self.buffer_capacity]                                                        #Getting the message from the buffer                                     
            self.chunk_counter = (self.chunk_counter + 1) % 65536                                                      #Incrementing the chunk_to_play

            sending_sock.sendto(package, (self.destination_IP_addr, self.destination_port))
            outdata[:] = numpy.reshape(message, (self.samples_per_chunk, self.number_of_channels))                  #Playing the audio recieved

            sys.stderr.write("."); sys.stderr.flush()

        with sd.Stream(
                samplerate=self.samples_per_second,
                blocksize=self.samples_per_chunk,
                dtype=self.dtype,
                channels=self.number_of_channels,
                callback=record_send_and_play):
            while True:
                receive_and_buffer()
        
    def add_args(self):
        parser = Intercom.add_args(self)
        parser.add_argument("-bc", "--buffer_capacity", help="Buffer capacity.", type=int, default=100)
        return parser

if __name__ == "__main__":
    intercom = IntercomBuffer()
    parser = intercom.add_args()
    args = parser.parse_args()
    intercom.init(args)
    intercom.run()