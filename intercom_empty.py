#Empty

import sounddevice as sd
import numpy as np
import struct
from intercom import Intercom
from intercom_binaural import Intercom_binaural

if __debug__:
    import sys

class Intercom_empty(Intercom_binaural):

    def init(self, args):
        Intercom_binaural.init(self, args)

    #...

    #...

if __name__ == "__main__":
    intercom = Intercom_empty()
    parser = intercom.add_args()
    args = parser.parse_args()
    intercom.init(args)
    intercom.run()