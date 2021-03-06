
import os, sys
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import matplotlib.image as mpimg
import numpy as np
from matplotlib.widgets import Button
import glob
from tempfile import TemporaryFile
import psycopg2

class Annotate(object):
    def __init__(self, image,name, imgid):
        self.img = image
        self.imgname = name
        self.imgid = imgid
        self.i = 1
        self.col = 'b' # deafult color for true positive label
        self.ax = plt.gca()
        # Initialize the Reactangle patch object with properties 
        self.rect = Rectangle((0,0), 1, 1, alpha = 1,ls = 'solid',fill = False, clip_on = True,color = self.col)
        # Initialize two diagonally opposite co-ordinates of reactangle as None
        self.xc = None
        self.yc = None
        self.x0 = None
        self.y0 = None
        self.x1 = None
        self.y1 = None
        self.height = None
        self.width = None
        self.mx0 = None
        self.my0 = None
        self.mx1 = None
        self.my1 = None
        self.sizeModifier = 2
        
        self.w = 30.0
        self.h = 40.0
        self.qkey = None

        #self.centers
        # The list that will store value of those two co-ordinates of 
        # all the patches for storing into the file later
        self.xy = []
        self.ax.add_patch(self.rect)
        # Initialize mpl connect object 
        connect = self.ax.figure.canvas.mpl_connect
        # Create objects that will handle user initiated events 
        # We are using three events 
        # First event is button press event (on left key click)- 
        # on which on_click function is called
        connect('button_press_event', self.on_click)
        connect('close_event', self.handle_close)
        
        
        # Second event to draw, in case a mistake in labelling is made, 
        # deleting the patch requires redrawing the original canvas
        self.draw_cid = connect('draw_event', self.grab_background)
        
        # Third event - key press event
        # To change color of the patches when you want to switch between 
        # true postive and false postive labels
        connect('key_press_event',self.colorChange)
 



    def objCreation(self):
        # The new reactangle object to use after blit function (clearing 
        # the canvas and removing rectangle objects)
        
        self.rect = Rectangle((0,0), 1, 1, alpha = 1,ls = 'solid',fill = False, clip_on = True)
        self.xc = None # x co-ordinate of patch center
        self.yc = None # y co-ordinate of patch center
        self.x0 = None # top left x co-ordinate of patch center
        self.y0 = None # top left y co-ordinate of patch center
        self.x1 = None # lower right y co-ordinate of patch center
        self.y1 = None # lower right y co-ordinate of patch center
        self.sizeModifier = 2 # The amount by which width/height will increase/decrease
        self.w = 30.0 # Initial width
        self.h = 40.0 # Initial height
        # Aspect Ratio of 3/4
        # Add the patch on the axes object of figure
        self.ax.add_patch(self.rect)  


    def deletePrevious(self):
        '''
        Deletes the latest patch that was drawn
        '''
        # Clear the screen by calling blit function
        self.blit()
        # Remove the last patch co-ordinates from the list
        self.xy = self.xy[:-1]


        # Redraw all the rects except the previous ones
        for coords in self.xy:
            self.rect.set_width(coords[2] - coords[0])
            self.rect.set_height(coords[3] - coords[1])
            self.rect.set_xy((coords[0], coords[1]))
            self.rect.set_color(coords[4])
            self.ax.draw_artist(self.rect)
            self.ax.figure.canvas.blit(self.ax.bbox)

    def resize(self,det):
        '''
        Resizing at the same center, maintaing the same aspect ratio
        and using key only (without dragging)
        '''

        # Resizing without dragging requires deleting previous patch
        # Saving the center, width, height of the patch before deleting it
        # As it will be used for reconstructing with increased/decreased size
       
        last_obj = self.xy[-1]
        # print last_obj
        xc = last_obj[-2]
        yc = last_obj[-1]
        col = last_obj[-3]
        w = last_obj[2] - last_obj[0]
        h = last_obj[3] - last_obj[1]

        self.deletePrevious()
        self.xc = xc
        self.yc = yc
        self.col = col
        
        self.w = w*det 
        print self.w
        
        self.h =  h*det
        
        self.drawRect()

    def handle_close(self,event):
        '''
        if you ended up closing the plot using the plot's X button instead of 'q' key
        '''
        if self.qkey != 'q':
            self.close_plot()
    
    def skipCrowd(self):
	'''Function to skip crowded scene, label them as crowd in the db'''

        conn = psycopg2.connect("dbname='dot_pub_cams'")
        cursor = conn.cursor()
        cursor.execute("""UPDATE images SET labeled=TRUE, set_type='crowd' WHERE id=%s""" % (self.imgid))

        # Closing db connections
        conn.commit()
        cursor.close()
        conn.close()

        plt.close()
        
    def close_plot(self):
        '''
        saving numpy patches and co-ordinates of the patches 
        '''
        print 'close'
        header = open('log.txt','a')
        header.write("Image id:%s" % (self.imgid))
 
 	#Blue Bounding Boxes
        blue_patches = filter(lambda x: x[4]=='b',self.xy)
        
        ##print self.xy
        #Saving to database
        conn = psycopg2.connect("dbname='dot_pub_cams'")
        cursor = conn.cursor()
        blueCount = 0
        for blue_patch_list in blue_patches:
            if len(blue_patch_list) <4:
	        continue	
	    topx = blue_patch_list[0]
	    topy = blue_patch_list[1]
	    botx = blue_patch_list[2]
	    boty = blue_patch_list[3]
	    	
            patch_array = self.img[topy:boty,topx:botx]
            if 0 not in np.shape(patch_array):
            	patch_path = self.imgname[:-4] + '_pos_' + str(blueCount) + '.npy'  
                blueCount+=1
                cursor.execute("""INSERT INTO labels 
                              (image, topx, topy, botx, boty, 
                               label, patch_path, type )
                              VALUES
                              (%s, %s, %s, %s, %s, %s, '%s', '%s') 
                              """ % (self.imgid, topx, topy, botx, boty, 1, patch_path, "pos"))

                np.save(patch_path, patch_array)
                os.chmod(patch_path, 0777)
                header.write("%s" % self.imgname+',')
                for item in blue_patch_list[:5]:
                    header.write("%s" % item+',')
                header.write('\n')
	
        cursor.execute("""UPDATE images SET labeled=TRUE, ped_count=%s WHERE id=%s""" % (blueCount, self.imgid))
        
        red_patches = filter(lambda x: x[4]=='r',self.xy)
        for i, red_patch_list in enumerate(red_patches):
            if len(red_patch_list) <4:
                continue
            topx = red_patch_list[0]
            topy = red_patch_list[1]
            botx = red_patch_list[2]
            boty = red_patch_list[3]
            
            patch_array = self.img[topy:boty,topx:botx]
            if 0 in np.shape(patch_array):
            	i-=1
            if 0 not in np.shape(patch_array):
            	patch_path = self.imgname[:-4] + '_neg_' + str(i) + '.npy' 
            	
                cursor.execute("""INSERT INTO labels 
                              (image, topx, topy, botx, boty, 
                               label, patch_path, type )
                              VALUES
                              (%s, %s, %s, %s, %s, %s, '%s', '%s') 
                              """ % (self.imgid, topx, topy, botx, boty, 1, patch_path, "neg"))

                np.save(patch_path, patch_array)
                os.chmod(patch_path, 0777)
                header.write("%s" % self.imgname+',')
                for item in red_patch_list[:5]:
                    header.write("%s" % item+',')
                header.write('\n')
        

        # Closing db connections
        conn.commit()
        cursor.close()
        conn.close()

        plt.close()


        
    def colorChange(self,event):
        '''
        To change color to take  false positves into consideration - the default is color blue for true postive
        '''
        
        print('press', event.key)
        sys.stdout.flush()
        if event.key == 'r': # red color
            # When 'r' key is pressed, the color of the next patch will be red
            self.col = 'r'
           

        elif event.key == 'b': # blue color
            # When 'b' key is pressed, the color of the next patch will be blue
            self.col = 'b' 

        # Optional setting for drawing patched using spacebar
        # elif event.key == ' ':
        #     self.on_click(event)    
            
        elif event.key == 'e': # escape
            # When 'e' key is pressed, escape the image label it as crowd
            self.skipCrowd()
            
        elif event.key == 't': # skip
            # When 'e' key is pressed, escape the image label it as crowd
            plt.close()
            
        elif event.key == 'd': # delete
            # When 'd' key is pressed, the latest patch drawn is deleted
            self.deletePrevious()

        elif event.key == 'c': # clear 
            # When 'c' key is pressed, all the patches are cleared, only orignal background is present
            self.blit()    
            self.xy = []
            # Flush out the list as we don't want to consider any patch co-ordinates

        elif event.key == 'tab':
            # use tab to increase the aspect ratio of the patch 

            self.resize(1.2)

        elif event.key == 'control':
            # use control key to decrease the aspect ratio of the patch
            self.resize(0.95)

        elif event.key == '2':
            # use control key to decrease the aspect ratio of the patch
            self.resize(0.85)

        elif event.key == '3':
            # use control key to decrease the aspect ratio of the patch
            self.resize(0.50)  

        
        elif event.key == 'q': # quit plot, show up the next
            # save necessary labels and close the plot
            self.qkey = 'q'
            self.close_plot()
                
        elif event.key == '0':
            sys.exit()
    
    def on_click(self, event):
        '''
        Using two diagonally opposite clicks to draw a reactangle 
        '''
       
       
        self.i = self.i + 1
        if self.i%2 == 0:
            # The first click to mark one point of the rectangle and save the coordinates 
            print 'click1'
            self.mx0 = event.xdata
            self.my0 =  event.ydata

        if self.i%2 == 1:    
            # on second click - the rectangle should show up
   
            print 'click2'
            self.mx1 = event.xdata
            self.my1 = event.ydata
            self.drawRect()


       

    def drawRect(self):
        
        self.mx0, self.y0 = (self.mx0, self.my0) if (self.my1>self.my0) else (self.mx1,self.my1)
        self.mx1, self.y1 = (self.mx0, self.my0) if (self.my1<self.my0) else (self.mx1,self.my1)
        
        # Set the two diagonally opposite co-ordinates of the patch  by width and height
       
    
        self.height = self.y1 - self.y0
        self.width = 3.0/4.0 * self.height

        self.x0 = self.mx0 - self.width/2
        self.x1 = self.mx0 + self.width/2
        print self.x0, self.x1


        
        self.xy.append([self.x0,self.y0,self.x1,self.y1,self.col])
        print self.xy
        
        # Set the width and height of the rectangle patch as these two alone can characterize the patch
        self.rect.set_width(self.width)
        self.rect.set_height(self.height)
        self.rect.set_xy((self.x0, self.y0))
        # Set the color of the reactangle - can be blue/red depending on postive/negative label respectively
        self.rect.set_color(self.col)
        self.ax.draw_artist(self.rect)
        # Blit is used to successively retain and display patches on the screen 
        # Else Successively drawing one patch will remove the last drawn patch 
        self.ax.figure.canvas.blit(self.ax.bbox)

    # The following three functions taken from 
    # http://stackoverflow.com/questions/29277080/efficient-matplotlib-redrawing

    def safe_draw(self):
        """Temporarily disconnect the draw_event callback to avoid recursion"""
        canvas = self.ax.figure.canvas
        canvas.mpl_disconnect(self.draw_cid)
        canvas.draw()
        self.draw_cid = canvas.mpl_connect('draw_event', self.grab_background)


    def grab_background(self, event=None):
        """
        When the figure is resized, hide the rect, draw everything,
        and update the background.
        """
        self.rect.set_visible(False)
        self.safe_draw()

        # With most backends (e.g. TkAgg), we could grab (and refresh, in
        # self.blit) self.ax.bbox instead of self.fig.bbox, but Qt4Agg, and
        # some others, requires us to update the _full_ canvas, instead.
        self.background = self.ax.figure.canvas.copy_from_bbox(self.ax.figure.bbox)
        self.rect.set_visible(True)
        # self.blit()

    

    def blit(self):
        """
        Efficiently update the figure, without needing to redraw the
        "background" artists.
        """
        self.objCreation()
        self.ax.figure.canvas.restore_region(self.background)
        self.ax.draw_artist(self.rect)
        self.ax.figure.canvas.blit(self.ax.figure.bbox)


if __name__ == '__main__':

    def main(imgname, imgid):    
        img = mpimg.imread(imgname)
        # Create the canvas
        fig = plt.figure()
        ax = fig.add_subplot(111)
        # print type(img)
        ax.imshow(img)
        a = Annotate(img, imgname, imgid)

        plt.show()
    
    while(1):  
	conn = psycopg2.connect("dbname='dot_pub_cams'")
        cursor = conn.cursor()
        cursor.execute("""select * from images where labeled=false and id=%s limit 1;"""%(np.random.randint(68250, 177561, 1)[0]))

        image_fields = cursor.fetchall()
        #If random image has been labeled before, then select new random image
        if len(image_fields) == 0:
            continue 
	image_fields = image_fields[0]
        imgname = str(image_fields[-5]) + str(image_fields[2])
	imgid = image_fields[1]
	# Closing db connections
        cursor.close()
        conn.close()
        
        main(imgname, imgid)



