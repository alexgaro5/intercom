import sounddevice as sd                                                        # https://python-sounddevice.readthedocs.io
import numpy                                                                    # https://numpy.org/
import struct
from intercom import Intercom                                                                                                                 #Importing the original Intercom
if __debug__:
   import sys

class IntercomBuffer(Intercom):

    MAX_CHUNK_NUMBER = 65536
                                                                                                                                              #Redifining the init method
    def init(self, args):
        Intercom.init(self, args)
        self.chunks_to_buffer = args.chunks_to_buffer
        self.cells_in_buffer = self.chunks_to_buffer * 2
        self._buffer = [self.generate_zero_chunk()] * self.cells_in_buffer
        self.packet_format = f"H{self.samples_per_chunk}h"

        if __debug__:
            print(f"chunks_to_buffer={self.chunks_to_buffer}")

    def run(self):

        self.recorded_chunk_number = 0
        self.played_chunk_number = 0

        def receive_and_buffer():
            package, source_address = self.receiving_sock.recvfrom(Intercom.MAX_MESSAGE_SIZE)                                                   #We recieve the message via UDP

            chunk_number, *message = struct.unpack(self.packet_format, package)                                                                 #Unpacking the message recieved 

            self._buffer[chunk_number % self.cells_in_buffer] = numpy.asarray(message).reshape(self.frames_per_chunk, self.number_of_channels)  #Inserting the data audio in the buffer
            return chunk_number                                                                                                                 #Return the chunk number

        def record_send_and_play (indata, outdata, frames, time, status):                                                       
            package = struct.pack(self.packet_format, self.recorded_chunk_number, *(indata.flatten()))                                          #Packing the message to send
            self.recorded_chunk_number = (self.recorded_chunk_number + 1) % self.MAX_CHUNK_NUMBER                                               #Increase the index to record the chunk
            
            self.sending_sock.sendto(package, (self.destination_IP_addr, self.destination_port))                                                #Send the message

            message = self._buffer[self.played_chunk_number % self.cells_in_buffer]                                                             #Getting the message from the buffer                                     
            self._buffer[self.played_chunk_number % self.cells_in_buffer] = self.generate_zero_chunk()                                          #Put zeros in the index position where we take the previuos message
            self.played_chunk_number = (self.played_chunk_number + 1) % self.cells_in_buffer                                                    #Increase the index to play the chunk

            outdata[:] = message                                                                                                                #Playing the audio recieved

            if __debug__:
               sys.stderr.write("."); sys.stderr.flush()

        with sd.Stream(samplerate=self.frames_per_second, blocksize=self.frames_per_chunk, dtype=numpy.int16, channels=self.number_of_channels, callback=record_send_and_play):
            print("-=- Press CTRL + c to quit -=-")
            first_received_chunk_number = receive_and_buffer()
            self.played_chunk_number = (first_received_chunk_number - self.chunks_to_buffer) % self.cells_in_buffer
            while True:
                receive_and_buffer()

    def add_args(self):
        parser = Intercom.add_args(self)
        parser.add_argument("-cb", "--chunks_to_buffer", help="Number of chunks to buffer", type=int, default=32)
        return parser

if __name__ == "__main__":
    intercom = IntercomBuffer()
    parser = intercom.add_args()
    args = parser.parse_args()
    intercom.init(args)
    intercom.run()