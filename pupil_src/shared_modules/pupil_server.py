'''
(*)~----------------------------------------------------------------------------------
 Pupil - eye tracking platform
 Copyright (C) 2012-2014  Pupil Labs

 Distributed under the terms of the CC BY-NC-SA License.
 License details are in the file license.txt, distributed as part of this software.
----------------------------------------------------------------------------------~(*)
'''

import atb
import numpy as np
from gl_utils import draw_gl_polyline_norm
from ctypes import c_float,c_int,create_string_buffer

import cv2
import zmq
from plugin import Plugin
import time
import json

import logging
logger = logging.getLogger(__name__)



class Pupil_Server(Plugin):
    """Calibration results visualization plugin"""
    def __init__(self, g_pool, atb_pos=(10,400)):
        Plugin.__init__(self)

        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUB)
        self.address = create_string_buffer("tcp://127.0.0.1:5000",512)
        self.set_server(self.address)

        help_str = "Pupil Message server: Using ZMQ and the *Publish-Subscribe* scheme"

        self._bar = atb.Bar(name = self.__class__.__name__, label='Server',
            help=help_str, color=(50, 50, 50), alpha=100,
            text='light', position=atb_pos,refresh=.3, size=(300,40))
        self._bar.define("valueswidth=170")
        self._bar.add_var("server address",self.address, getter=lambda:self.address, setter=self.set_server)
        self._bar.add_button("close", self.close)

        self.exclude_list = ['ellipse','pos_in_roi','major','minor','axes','angle','center']

    def set_server(self,new_address):
        try:
            self.socket.bind(new_address.value)
            self.address.value = new_address.value
        except zmq.ZMQError:
            logger.error("Could not set Socket.")

    def update(self,frame,recent_pupil_positions,events):   
        t_interval = .05    # in seconds

        ## Determine if new frame should be sent to client
        try:
            curr_time = time.time()
            send_image = curr_time - self.last_frame_sent > t_interval            
            if send_image:
                self.last_frame_sent = curr_time
        except:
            # if no last_frame_sent var exists an exception is raised. Initialize everything
            self.last_frame_sent = curr_time
            send_image = True
					
        # Check if pupil data should be sent
        if len(recent_pupil_positions):
            msg = "Pupil\n"    
            for p in recent_pupil_positions:                
                for key,value in p.iteritems():
                    if key not in self.exclude_list:
                        msg +=key+":"+str(value)+'\n'
            self.socket.send( msg, zmq.SNDMORE )
        else:
            self.socket.send( "None", zmq.SNDMORE )

        # Check if event data should be sent
        if len(events):
            msg = 'Event'+'\n'
            for e in events:                
                for key,value in e.iteritems():
                    if key not in self.exclude_list:
                        msg +=key+":"+str(value).replace('\n','')+'\n'
            self.socket.send( msg, zmq.SNDMORE )
        else:
            self.socket.send( "None", zmq.SNDMORE )								

        # Send image data, if applicable
        # ZMQ allows to send a numpy array directly over a socket
        # You do need to send metadata about the image to the client, so it can 
        # reconstruct it there
        if send_image:
            metadata = dict(
                dtype=str(frame.img.dtype),
                shape=frame.img.shape
            )
            self.socket.send_json(metadata, zmq.SNDMORE)
            self.socket.send(frame.img, zmq.SNDMORE, copy=True, track=False)
        else:
            self.socket.send( "None", zmq.SNDMORE )
            self.socket.send( "None" )


    def close(self):
        self.alive = False

    def cleanup(self):
        """gets called when the plugin get terminated.
           either volunatily or forced.
        """
        self._bar.destroy()
        self.context.destroy()

