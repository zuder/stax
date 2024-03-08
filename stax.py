# -*- coding: utf-8 -*-
#----------------------------------------------------------------------------
# v1.0
#----------------------------------------------------------------------------
'''Simple crypt module'''

import os
import datetime
import warnings
import managers
import time
from glanceclient.common import utils as glanceUtils
from cinderclient import utils as cinderUtils
from glanceclient.common import progressbar
import prettytable
import getopt
import ConfigParser
import gzip
import shutil
from collections import OrderedDict
from time import sleep
import logger
import sys
import shared
from simplecrypt import decrypt as simpleDecrypt

APP_VER = 'Stax 1.0'
APP_DESC = 'OpenStack backup automation'
APP_AUTH = ''
SPIN = ["|", "/" , "-", "\\" ]

class Config:
    def __init__(self):

        '''Construnctor - identify and read config file'''
        if sys.argv[0].find('.') > 0:
            self.file = sys.argv[0][:sys.argv[0].find('.')] + '.ini'
        else:
            self.file = sys.argv[0] + '.ini'
        try:
            self.cfg = ConfigParser.ConfigParser()
            with open(self.file) as f:
                self.cfg.readfp(f)
        except IOError:
            print "Cannot open config file %s!" % self.file
            sys.exit(1)

        try:
            shared.PROFILE = str(self.cfg.get('INIT', 'PROFILE'))
            shared.LOG_LEVEL = str(self.cfg.get('INIT', 'LOG_LEVEL'))
            shared.CHK_STATE_INT = int(self.cfg.get('INIT', 'CHK_STATE_INT'))
            shared.CHK_STATE_RET = int(self.cfg.get('INIT', 'CHK_STATE_RET'))
            shared.CHK_IMG_INT = int(self.cfg.get('INIT', 'CHK_IMG_INT'))
            shared.COMPRESS = str(self.cfg.get('INIT', 'COMPRESS'))
            shared.OS_USER_NAME = str(self.cfg.get(shared.PROFILE, 'OS_USER_NAME'))
            shared.OS_PROJECT_NAME = str(self.cfg.get(shared.PROFILE, 'OS_PROJECT_NAME'))
            shared.OS_AUTH_URL = str(self.cfg.get(shared.PROFILE, 'OS_AUTH_URL'))
            shared.OS_USER_DOMAIN_NAME = str(self.cfg.get(shared.PROFILE, 'OS_USER_DOMAIN_NAME'))
            shared.OS_PROJECT_DOMAIN_NAME = str(self.cfg.get(shared.PROFILE, 'OS_PROJECT_DOMAIN_NAME'))
            shared.PWD_FILE = str(self.cfg.get(shared.PROFILE, 'PWD_FILE'))

        except Exception as ex:
            print "Cannot parse config file %s! %s" % (self.file, str(ex))
            sys.exit(1)

class Stax(object):
    '''Main application class'''

    def __init__(self):
        '''Constructor'''
        warnings.filterwarnings("ignore")
        c = Config()
        logger.configure()
        logger.log = logger.logging.getLogger("stax")
        logger.log.info("Reading config file [%s]" % c.file )
        self.decrypt(shared.PWD_FILE)

    def authorize(self):
        try:
            keystoneConn = managers.ConnectionManager(shared.OS_AUTH_URL, shared.OS_USER_NAME, shared.OS_PASSWORD,shared.OS_PROJECT_NAME, shared.OS_PROJECT_DOMAIN_NAME, shared.OS_USER_DOMAIN_NAME)
            self.cinder = managers.CinderManager(keystoneConn.getSession())
            self.nova = managers.NovaManager(keystoneConn.getSession())
            self.glance = managers.GlanceManager(keystoneConn.getSession())

        except Exception as ex:
            logger.log.error("Cannot connect!")
            logger.log.error( str(ex))
            raise


    def saveImage(self,p_imageId, p_outputFile):
        try:
            imageFile = open(p_outputFile, 'w+')
            body = self.glance.getData(p_imageId)

            #print len(body)
            body = progressbar.VerboseIteratorWrapper(body, len(body))
            glanceUtils.save_image(body, p_outputFile)
            for chunk in body :
                imageFile.write(chunk)
            logger.log.info('Image saved as %s' % p_outputFile)
        except Exception as ex:

            logger.log.error("Cannot save image to local as %s" % p_outputFile)
            logger.log.error( str(ex))
            raise
    def reportServers(self):
        table = prettytable.PrettyTable(['Id', 'Instance Name','Status', 'Image Name','Size', 'Key Pair','Network'])
        #table._set_align('l')
        for server in self.nova.listServers():
            image_name = str()
            if any(server.image):
                image_name = self.glance.getImage(server.image['id']).name
            flavor = self.nova.gatFlavor(server.flavor['id'])
            networks = self.nova.formatNetwork(server.addresses)

            table.add_row([server.id,
                           server.name,
                           server.status,
                           image_name,
                           self.nova.formatSize(flavor),
                           server.key_name,
                           networks])
        print('\n\nINSTANCES')
        print(table)

    def progLoop(self, text):
        sys.stdout.write('\r')
        sys.stdout.write(text)
        sys.stdout.flush()

    def getTS(self):
        return '{:%Y%m%d%H%M}'.format(datetime.datetime.now())

    def reportVolumes(self):
        columns = ['Id','Name', 'Status' ,'Size', 'Volume Type', 'Bootable','Attached to','Created At']
        volumes = self.cinder.listVolumes()
        for v in volumes:
            servers = [s.get('server_id') for s in v.attachments]
            setattr(v, 'attached_to', ','.join(map(str, servers)))
        print('\n\nVOLUMES')
        cinderUtils.print_list(volumes, columns, {})

    def reportVolumesSnapshots(self):
        columns = ['ID','Name', 'Volume ID', 'Status', 'Created at', 'Size']
        print('\n\nVOLUMES SNAPSHOTS')
        cinderUtils.print_list(self.cinder.listSnapshots(), columns, {})

    def reportImages(self):
        columns = ['Id', 'Name', 'Disk Format','Container Format', 'Size', 'Status','Created At', 'Updated At']
        projectImages = self.glance.listImages()

        snapshots = []
        prvImages = []
        pubImages = []
        for image in projectImages:
            if 'image_location' in image:
                snapshots.append(image)
            else:
                if 'visibility' in image and image['visibility'] == 'private':
                    prvImages.append(image)
                else:
                    pubImages.append(image)

        print('\n\nPUBLIC IMAGES')
        glanceUtils.print_list(pubImages, columns)

        print('\n\nPRIVATE IMAGES')
        glanceUtils.print_list(prvImages, columns)

        print('\n\nSNAPSHOTS')
        glanceUtils.print_list(snapshots, columns)


    def pauseInstance(self, p_srvId):
        logger.log.info('Trying to pause instance')
        if self.nova.getInstanceStatus(p_srvId) == 'paused':
            logger.log.info('Instance already paused, skipping pausing')
        else:
            cnt = 1
            try:
                logger.log.debug("Current status: %s" % self.nova.getInstanceStatus(p_srvId))
                self.nova.pauseServer(p_srvId)
                while self.nova.getInstanceStatus(p_srvId) != 'paused':
                    logger.log.debug("Current status: %s" % self.nova.getInstanceStatus(p_srvId))
                    self.progLoop(SPIN[cnt%len(SPIN)])
                    cnt += 1
                    if cnt > shared.CHK_STATE_RET:
                        logger.log.warning("Cannot pause instance during %ss - giving up" % str(shared.CHK_STATE_INT*shared.CHK_STATE_RET))
                        return
                    sleep(shared.CHK_STATE_INT)
                self.progLoop("")
                logger.log.info('Instance paused successfully')
            except:
                logger.log.warning('Proceeding anyway')
            finally:
                logger.log.debug("Current status: %s" % self.nova.getInstanceStatus(p_srvId))

    def resumeInstance(self, p_srvId):
        logger.log.info("Attempting to resume instance")
        if self.nova.getInstanceStatus(p_srvId) != 'paused':
            logger.log.info('Instance is not paused [%s], nothing to resume')
        try:
            logger.log.debug("Current status: %s" % self.nova.getInstanceStatus(p_srvId))
            self.nova.resumeServer(p_srvId)
            cnt = 1
            while self.nova.getInstanceStatus(p_srvId) == 'paused':
                logger.log.debug("Current status: %s" % self.nova.getInstanceStatus(p_srvId))
                self.progLoop(SPIN[cnt%len(SPIN)])
                cnt += 1
                if cnt > shared.CHK_STATE_RET:
                    logger.log.warning("Cannot resume instance during %ss - giving up" % str(shared.CHK_STATE_INT*shared.CHK_STATE_RET))
                    return
                sleep(shared.CHK_STATE_INT)
            self.progLoop("")
            logger.log.info('Instance resumed successfully')
        except:
            logger.log.warning('Proceeding anyway')
        finally:
            logger.log.debug("Current status: %s" % self.nova.getInstanceStatus(p_srvId))

    def decrypt(self, p_file):
        '''Decodes file'''
        try:
            with open(p_file, 'rb') as content_file:
                txt = content_file.read()
            logger.log.info("Decrypting login credentials [%s]" % p_file)
            shared.OS_PASSWORD = simpleDecrypt('PUT_YOUR_PASS_USED_DURING_PASSWORD_ENCRYPTION_HERE', txt)
        except Exception as ex:
            logger.log.error("Cannot decrypt password! %s" % str(ex))

    def downloadImages(self, p_imageList, p_compress=True, p_deleteLocal=True, p_deleteRemote=True):

        for imgId in p_imageList:
            imageName = self.glance.getImage(imgId).name

            logger.log.info("Downloading image %s" % imgId)

            tf = imageName +'.img'

            self.saveImage(imgId, tf)

            if p_deleteRemote:
                self.removeImageFromCloud(imgId)

            if p_compress and shared.COMPRESS.lower() == 'true':
                self.compressFile(tf)

                if p_deleteLocal:
                    self.removeLocalFile(tf)


    def removeImageFromCloud(self, p_ImageId):
        try:
            imageName = self.glance.getImage(p_ImageId).name
            logger.log.info('Trying to remove image %s from cloud' % (imageName))
            self.glance.deleteImage(p_ImageId)
            logger.log.info("Image removed successfully")
        except Exception as ex:
            logger.log.error("Cannot remove image from cloud! %s" % str(ex))

    def detachVolume(self, p_srvId, p_volId):
        logger.log.info('Trying to detach volume')
        try:
            #cinder api in fact is not physically detaching volume, only updates its state. True detachment can be achived with nova api:
            #self.nova.detachVolume(p_srvId,p_volId)
            #however we don't need to detach volume since instance is paused
            self.cinder.detachVol(p_volId)

            cnt=1
            while self.cinder.getVolume(p_volId).status!= 'available':
                logger.log.debug("Current status: %s" % self.cinder.getVolume(p_volId).status)
                self.progLoop(SPIN[cnt%len(SPIN)])
                cnt += 1
                if cnt > shared.CHK_STATE_RET:
                    logger.log.warning("Cannot detach volume during %ss - giving up" % str(shared.CHK_STATE_INT*shared.CHK_STATE_RET))
                    return
                sleep(shared.CHK_STATE_INT)
            self.progLoop("")
            logger.log.info('Volume detached successfully')
            logger.log.debug("Attached volumes: %s" % (self.nova.getAttachedVolumes(p_srvId)))
        except Exception as ex:
            logger.log.warning(str(ex))
            logger.log.warning('Proceeding anyway')

    def attachVolume(self, p_volId, p_srvId, p_device, p_hostName):
        try:
            logger.log.info("Trying to reattach volume to instance %s, device [%s]" % (p_srvId,p_device))

            #same comment as with detach function - for true attachment use:
            #self.nova.createVolume(p_srvId,p_volId,p_device)
            self.cinder.attachVol(p_volId, p_srvId, p_device, p_hostName)

            cnt = 1
            while self.cinder.getVolume(p_volId).status=='available':
                logger.log.debug("Current status: %s" % self.cinder.getVolume(p_volId).status)
                self.progLoop(SPIN[cnt%len(SPIN)])
                cnt += 1
                if cnt > shared.CHK_STATE_RET:
                    logger.log.warning("Cannot attach volume during %ss - giving up" % str(shared.CHK_STATE_INT*shared.CHK_STATE_RET))
                    return
                sleep(shared.CHK_STATE_INT)
            self.progLoop("")
            logger.log.info('Volume attached successfully')
            logger.log.debug("Attached volumes: %s" % (self.nova.getAttachedVolumes(p_srvId)))
        except Exception as ex:
            logger.log.warning(str(ex))
            logger.log.warning('Proceeding anyway')

    def backupVolumeWithSnaphot(self, p_vol):

        if len(p_vol.attachments)> 0:
            for i in p_vol.attachments:
                self.pauseInstance(i['server_id'])

            #detach volume, wait until done
                self.detachVolume(i['server_id'], p_vol.id)
        else:
            logger.log.info("Volume not attached")

    def cleanVolAfterBackup(self, p_vol):
        if len(p_vol.attachments)> 0:
            #resume instance(s)
            for i in p_vol.attachments:
                self.resumeInstance(i['server_id'])

            for i in p_vol.attachments:
                self.attachVolume(p_vol.id,i['server_id'],i['device'],i['host_name'])


    def verifyAttachments(self, p_volList, p_srvId):

        attachedVolumes=[]
        for x in p_volList:
            try:
                logger.log.info("Analysing volume %s" % (x))
                if self.cinder.getVolume(x)._info["attachments"]:
                    logger.log.debug("Volume exists in cloud, checking attachments")
                    for y in self.cinder.getVolume(x)._info["attachments"]:
                        logger.log.debug("Volume instance property: %s" % (y['server_id']))
                        if y['server_id'] != p_srvId:
                            logger.log.warning("Malformed instance property! Volume in fact attached to another instance (%s)!" % (y['server_id']))
                            logger.log.warning("Excluding volume from backupset")

                        else:
                            logger.log.info("Volume and instance information consistent, adding volume to backupset")
                            attachedVolumes.append(x)
                else:
                    logger.log.warning("Volume in fact not attached to any instance. Excluding volume from backupset")

            except:
                logger.log.warning("Instance property contains outdated volume information")
                logger.log.warning("Volume probably already removed from cloud. Excluding volume from backupset")

        logger.log.info("Volume analysis completed")
        return attachedVolumes

    def waitForImgCreation(self,p_imgId):
        cnt = 1
        while self.glance.getImage(p_imgId)['status']!= 'active':
            logger.log.debug("Current status: %s" % self.glance.getImage(p_imgId)['status'])
            self.progLoop(SPIN[cnt%len(SPIN)])
            cnt += 1
            sleep(shared.CHK_IMG_INT)
        self.progLoop("")
        sleep(shared.CHK_IMG_INT)
        logger.log.info('Image created')

    def waitForSnapCreation(self,p_snapId):
        cnt = 1
        while self.cinder.getSnapshot(p_snapId).status!= 'available':
            logger.log.debug("Current status: %s" % self.cinder.getSnapshot(p_snapId).status)
            self.progLoop(SPIN[cnt%len(SPIN)])
            cnt += 1
            sleep(shared.CHK_IMG_INT)
        self.progLoop("")
        sleep(shared.CHK_IMG_INT)
        logger.log.info('Snapshot created')

    def waitForVolCreation(self,p_volId):
        cnt = 1
        while self.cinder.getVolume(p_volId).status!= 'available':
            logger.log.debug("Current status: %s" % self.cinder.getVolume(p_volId).status)
            self.progLoop(SPIN[cnt%len(SPIN)])
            cnt += 1
            sleep(shared.CHK_IMG_INT)
        self.progLoop("")
        sleep(shared.CHK_IMG_INT)
        logger.log.info('Volume created')

    def backupInstance(self, p_imageList, p_download, p_isAtomic=True, p_snap = True):

        #iterate through input list of instances p_imageList
        for srvId in p_imageList:
            try:
                n.emmit('BACKUP OF INSTANCE', srvId)

                srvName = self.nova.getInstance(srvId).name

                #array for storing volumes for backup
                backupImageList=[]
                #set new image name
                newImageName = '%s_inst_copy_%s' % (self.getTS(),srvName)
                #get volumes information from instance property
                attachedVolumesProperty = [str(item) for item in self.nova.getAttachedVolumes(srvId)]

                logger.log.info("Checking attached volumes")
                logger.log.info("Instance level volume information: %s" % (attachedVolumesProperty))

                attachedVolumes = self.verifyAttachments(attachedVolumesProperty, srvId)
                
                #pause instance, wait until paused
                self.pauseInstance(srvId)

                #create instance image
                logger.log.info("Creating image %s as copy of %s" % (newImageName, srvName))
                newImageId = self.nova.createImage(srvId, newImageName)
                #wait till it's done
                self.waitForImgCreation(newImageId)

                #record backup image id of instance
                backupImageList.append(newImageId)


                #backup attached volumes
                #atomic = backup only instance, otherwise backup also attached volumes
                if not p_isAtomic:

                    #if any volume is attached, proceed
                    if len(attachedVolumes) > 0:
                        logger.log.info('Executing backup of attached volumes %s' % attachedVolumes)

                        if not p_snap:
                            volumeAttachments={}
                            #for all attached volumes detach all volumes
                            for x in attachedVolumes:
                               vol = self.cinder.getVolume(x) #vol.id = x
                               if len(vol.attachments)>0:
                                    #record mount points in dictionary for futher remounting
                                    volumeAttachments[vol.id] =  dict(vol.attachments[0])
                               self.detachVolume(srvId, vol.id)

                        if not p_snap:
                            #backup all attached volumes, skip download (bulk download of all images will be performed at the and of procedure)
                            backupImageList = backupImageList + self.backupVolume(attachedVolumes, False, False)
                        else:
                            backupImageList = backupImageList + self.backupVolumeBySnaphot(attachedVolumes, False, False)

                        #then resume isntance
                        self.resumeInstance(srvId)

                        #finally remount volumes to their original locations     
                        if not p_snap:
                            for x in volumeAttachments:
                                logger.log.info("Remounting volume %s " % (x))
                                self.attachVolume(x,volumeAttachments[x]['server_id'],volumeAttachments[x]['device'],volumeAttachments[x]['host_name'])
                    else:
                        logger.log.info('Attached volumes not found, skipping volumes backup')
                        #self.resumeInstance(srvId)
                else:
                    logger.log.info('Skipping backup of attached volumes')
                    #resume isntance
                    self.resumeInstance(srvId)

                #download and compress images - instance + volumes
                if p_download:
                    logger.log.info('Collecting backupset to current folder')
                    n.downloadImages(backupImageList)
                logger.log.info('Backup of instance %s completed successfully!' % (srvId))
            except:
                logger.log.error("Terminating backup of instance %s due to critical error" % (srvId))


    def backupVolume(self, p_imageList, p_download, p_isAtomic=True):
        newImageList = []
        #iterate through input list of volumes p_imageList
        for volId in p_imageList:
            try:
                n.emmit('BACKUP OF VOLUME', volId + ' (USING FORCE DETACHING)')

                vol = self.cinder.getVolume(volId)
                sf = vol.name if vol.name !='' else vol.id

                #set new image name
                newImageName = '%s_vol_copy_%s' % (self.getTS(),sf)

                #atomic = pause instance(s) & detach if volume is attached, otherwise skip
                ## (volume backup called by instance backup = volume already detached, instance already paused)
                
                if p_isAtomic:
                    self.backupVolumeWithSnaphot(vol)

                #create volume image
                logger.log.info("Creating image %s as copy of volume %s" % (newImageName, sf))
                newImage = vol.upload_to_image('true',newImageName,'bare','raw')
                newImageId = newImage[1]['os-volume_upload_image']['image_id']

                #wait till it's done
                self.waitForImgCreation(newImageId)
                newImageList.append(newImageId)
                #atomic=reattach volume & resume instance(s)                
                if p_isAtomic:
                   self.cleanVolAfterBackup(vol)

                #download and compress instance image
                if p_download:
                    n.downloadImages([newImageId])

                logger.log.info('Backup of volume %s completed successfully!' % (volId))
            except:
                logger.log.error("Terminating backup of volume %s due to critical error" % (volId))
        return newImageList

    def backupVolumeBySnaphot(self, p_imageList, p_download, p_isAtomic=True):
        newImageList = []
        # iterate through input list of volumes p_imageList
        for volId in p_imageList:
            try:
                n.emmit('BACKUP OF VOLUME', volId + ' (USING SNAPSHOT AND TEMPORARY VOLUME)')

                vol = self.cinder.getVolume(volId)

                sf = vol.name if vol.name != '' else vol.id

                # set new image name
                newImageName = '%s_vol_copy_%s' % (self.getTS(), sf)
                snapName = newImageName + '.snap'

                logger.log.info("Creating temporary snapshot %s of volume %s" % (snapName, sf))
                snapshot = self.cinder.createSnapshot(volId, snapName)
                # wait till it's done
                self.waitForSnapCreation(snapshot.id)
                tmpVol = newImageName + '.tmp'
                logger.log.info("Creating temporary volume %s from snapthot %s" % (tmpVol, snapName))
                vol = self.cinder.createVolumeFromSnapshot(snapshot.id,snapshot.size,tmpVol)
                # wait till it's done
                self.waitForVolCreation(vol.id)

                # create volume image
                logger.log.info("Creating image %s as copy of temporary volume %s" % (newImageName, tmpVol))

                newImage = vol.upload_to_image('true', newImageName, 'bare', 'raw')
                newImageId = newImage[1]['os-volume_upload_image']['image_id']

                # wait till it's done
                self.waitForImgCreation(newImageId)
                newImageList.append(newImageId)
                logger.log.info("Removing temporary volume %s" % (snapName))
                self.cinder.deleteVolume(vol)
                time.sleep(10)
                logger.log.info("Removing temporary snapshot %s" % (snapName))
                self.cinder.deleteSnapshot(snapshot)

                # download and compress instance image
                if p_download:
                    n.downloadImages([newImageId])

                logger.log.info('Backup of volume %s completed successfully!' % (volId))

            except:
                logger.log.error("Terminating backup of volume %s due to critical error" % (volId))
        return newImageList
    def compressFile(self, p_file):

        try:
            cf = p_file+'.gz'
            logger.log.info("Compressing image")
            file = open(p_file, 'rb')
            body = progressbar.VerboseFileWrapper(file, glanceUtils.get_file_size(file))

            with gzip.open(cf, 'wb') as f_out:
                shutil.copyfileobj(body, f_out)
            print ""
            logger.log.info('Image compressed as %s' % cf)
        except Exception as ex:
            logger.log.error("Error during compression! %s" % str(ex))
            raise

    def removeLocalFile(self, p_file):
        try:
            logger.log.info("Removing local file %s" % (p_file))
            os.remove(p_file)
            logger.log.info("Local file removed" )
        except Exception as ex:
            logger.log.error("Cannot remove local file %s" % str(ex))
            raise

    def emmit(self,p_msg, p_obj):
        msg = "STARTING %s %s" % (p_msg, p_obj)
        logger.log.info('='*len(msg))
        logger.log.info(msg)
        logger.log.info('='*len(msg))

    def uploadImage(self, p_imageList):

        for imgFile in imageList:
            try:
                n.emmit('UPLOADING IMAGE', imgFile)
                file = open(imgFile, 'rb')
                body = progressbar.VerboseFileWrapper(file, glanceUtils.get_file_size(file))
                image = self.glance.createImage(os.path.basename(imgFile)+'.restored')
                self.glance.uploadImage(image.id, body)
                logger.log.info("Upload of image %s completed successfully!" % imgFile)
            except Exception as ex:
                logger.log.error("Error during image upload! %s" % str(ex))
                logger.log.error("Terminating upload of local image %s due to critical error" % imgFile)

    @staticmethod
    def printBanner():

        print '''
     _
    | |
 ___| |_ __ ___  __
/ __| __/ _` \ \/ /
\__ \ || (_| |>  <
|___/\__\__,_/_/\_\\

		'''
        print "\n%s - %s" % (APP_VER, APP_DESC)
        print"%s\n\n" % APP_AUTH
    def menu(self):

        menu = OrderedDict([
            ('1', 'List servers'),
            ('2', 'List images'),
            ('3', 'List volumes'),
            ('4', 'List volumes snapshots'),
            ('0', 'Exit')
        ])


        while True:
            Stax.printBanner()
            for key, value in menu.items():
                print('     (%s) %s' % (key, value))
            choice = raw_input('\n Select option >> ').lower().strip()

            if str(choice) in menu.keys():
                if choice == '0':
                    print "\nBye!\n"
                    sys.exit(0)
                elif choice == '1':
                    self.reportServers()
                elif choice == '2':
                    self.reportImages()
                elif choice == '3':
                    self.reportVolumes()
                elif choice == '4':
                    self.reportVolumesSnapshots()
                else:
                    print choice
                    self.menu()

    def getImgList(self, p_args, p_batchMode = False ):
        if len(p_args) == 0:
            return
        if p_batchMode:
            with open(p_args[0], 'r') as fl:
                imageList = list(fl.read().splitlines())
            imageList = [x for x in imageList if x != '']
            imageList = [x for x in imageList if x[:1] != '#']
        else:
            imageList = p_args
        return imageList

    @staticmethod
    def printHelp():
        '''Print help in stand alone mode'''
        Stax.printBanner()
        print "Usage: stax [-ijwvebdxupsr] [InstanceId|VolumeId|BatchFile]\n"
        print "     -i      backup instance with volumes (detach method)"
        print "     -j      backup instance with volumes (snapshot method)"
        print "     -w      backup volume (detach method)"
        print "     -v      backup volume (snapshot method)"
        print "     -e      backup instance only"
        print "     -b      batch file (bulk uuid's)"
        print "     -d      download cloud image"
        print "     -x      delete cloud image"
        print "     -u      upload local image to cloud"
        print "     -p      pause instance"
        print "     -s      resume instance"
        print "     -r      reporting mode"
        print ""
        sys.exit()

if __name__ == "__main__":

    opts, args = getopt.getopt(sys.argv[1:],"ijvwrbduepsx")
    if len(opts) == 0:
       Stax.printHelp()
       sys.exit()

    if not ((opts[0][0] == '-r')
            or (len(args)>0 and len(opts) in(1,2,3))
    ):
        Stax.printHelp()
    else:
        opts = [i[0] for i in opts]
        Stax.printBanner()
        n = Stax()
        n.authorize()

        if '-d' in opts:
            downloadImg = True
        else:
            downloadImg = False

        if '-b' in opts:
            batchMode = True
        else:
            batchMode = False

        logger.log.info("Batch file: %s; Image download: %s;" % (batchMode, downloadImg))
        imageList = n.getImgList(args,batchMode)

        if  '-r' in opts:
            n.menu()
        elif '-i' in opts:
            n.backupInstance(imageList,downloadImg,p_isAtomic=False, p_snap = False)

        elif '-j' in opts:
            n.backupInstance(imageList,downloadImg,p_isAtomic=False,p_snap = True)

        elif '-e' in opts:
            n.backupInstance(imageList,downloadImg,p_isAtomic=True)
        elif '-v' in opts:
            #backup of volume excluding instance
            n.backupVolumeBySnaphot(imageList,downloadImg,p_isAtomic=True)
        elif '-w' in opts:
            #backup of volume excluding instance
            n.backupVolume(imageList,downloadImg,p_isAtomic=True)
        elif '-d' in opts and len(opts)==1:
            for imgId in imageList:
                try:
                    n.emmit('DOWNLOAD OF IMAGE', imgId)
                    n.downloadImages([imgId], False, False, False)
                except:
                    logger.log.error("Terminating download of image %s due to critical error" % (imgId))

        elif '-u' in opts:
            n.uploadImage(imageList)
        elif '-p' in opts and len(opts)==1:
            for srvId in imageList:
                n.pauseInstance(srvId)
        elif '-s' in opts and len(opts)==1:
            for srvId in imageList:
                n.resumeInstance(srvId)
        elif '-x' in opts and len(opts)==1:
            for imgId in imageList:
                n.removeImageFromCloud(imgId)

        sys.exit()
