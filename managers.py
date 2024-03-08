from keystoneauth1.identity import v3
from keystoneauth1 import session
from keystoneclient.v3 import client
from glanceclient import Client as glanceClient
from cinderclient import client as cinderClient
from novaclient import client as novaClient
import logger

# do kompilacji konieczna zmiana na:
# from keystoneauth1.identity import v3
# from keystoneauth1 import session
# from keystoneclient.v3 import client
# from glanceclient.v2 import Client as glanceClient
# from cinderclient.v3 import client as cinderClient
# import novaclient.v2
# from novaclient import client as novaClient
# import logger

class ConnectionManager(object):
    """Cloud connection"""
    def __init__(self, p_auth_url, p_username, p_password, p_project_name, p_project_domain_name, p_user_domain_name ):
        auth = v3.Password(auth_url=p_auth_url,
                           username=p_username,
                           password=p_password,
                           project_name=p_project_name,
                           user_domain_name=p_user_domain_name,
                           project_domain_name=p_project_domain_name)
        sess = session.Session(auth=auth, verify=False)
        self.keystone = client.Client(session=sess, insecure=True)
        self.session = sess

    def getSession(self):
        return self.session

class NovaManager(object):
    """Nova module manager"""
    def __init__(self,p_sess):
        self.client = novaClient.Client('2',session=p_sess)
        logger.log = logger.logging.getLogger("stax")

    def formatNetwork(self, addresses):
        output = ''
        grp = ''
        for net, addr in addresses.items():
            if len(addr) > 0:

                for i in addr:
                    grp = "%s %s=%s," % (grp,net, i['addr'])
                if len(output):
                    output = '%s, %s' % (output, grp)
                else:
                    output = '%s' % grp
        return output.rstrip(',')

    def formatSize(self, flavor):
        res = divmod(flavor.ram, 1024)
        if res[0] == 0:
            ram = ' '.join([str(res[1]) + 'MB', 'RAM'])
        else:
            ram = ' '.join([str(res[0]) + 'GB', 'RAM'])
        vcpus = ' '.join([str(flavor.vcpus), 'VCPU'])
        disk = ' '.join([str(flavor.disk) + 'GB', 'Disk'])
        return ' | '.join([flavor.name, ram, vcpus, disk])

    def listServers(self):
        try:
            return self.client.servers.list()
        except Exception as ex:
            logger.log.error("Cannot list instances! %s" % str(ex))
            raise

    def getAttachedVolumes(self, p_srvId):
        try:
            #alternatively self.client.volumes.get_server_volumes(p_srvId)
            return [x['id'] for x in self.getInstance(p_srvId)._info['os-extended-volumes:volumes_attached']]
        except Exception as ex:
            logger.log.error("Cannot determine attached volumes! %s" % str(ex))
            raise

    def getInstance(self, p_srvId):
        try:
            return self.client.servers.get(p_srvId)
        except Exception as ex:
            logger.log.error("Cannot get instance details! %s" % str(ex))
            raise
    def getInstanceStatus(self,p_srvId):
        return self.getInstance(p_srvId).status.lower()
    def gatFlavor(self, id):
        return self.client.flavors.get(id)

    def listKeys(self):
        return self.client.keypairs.list()

    def pauseServer(self, p_srvId):
        srv = self.client.servers.get(p_srvId)
        try:
            srv.pause()
        except Exception as ex:
            logger.log.error("Cannot pause instance! %s" % str(ex))
            raise

    def detachVolume(self,p_srvId,p_attachmentId):
        #do not use
        self.client.volumes.delete_server_volume(p_srvId,p_attachmentId)

    def createVolume(self,p_srvId, p_volId, p_mountPoint):
        #do not use
        self.client.volumes.create_server_volume(p_srvId,p_volId,p_mountPoint)

    def resumeServer(self, p_srvId):
        srv = self.client.servers.get(p_srvId)
        try:
            srv.unpause()
        except Exception as ex:
            logger.log.error("Cannot resume instance! %s" % str(ex))
            raise

    def createImage(self, p_srvId, p_Label):
        try:
            srv = self.client.servers.get(p_srvId)

            newImageId = srv.create_image(p_Label)
            return newImageId
        except Exception as ex:
            logger.log.error("Cannot create image %s!" % str(ex))
            raise

class CinderManager(object):
    """Cinder module manager"""

    def __init__(self, p_sess):
        self.client = cinderClient.Client('3', session=p_sess)


    def listVolumes(self):
        return self.client.volumes.list()

    def listBackups(self):
        return self.client.backups.list()

    def listSnapshots(self):
        return self.client.volume_snapshots.list()

    def createSnapshot(self, p_volId, p_snapName):
        return self.client.volume_snapshots.create(p_volId, force=True, name=p_snapName)

    def deleteSnapshot(self, p_snap):
        return self.client.volume_snapshots.delete(p_snap)

    def createVolumeFromSnapshot(self, p_snapId, p_size, p_volName):
        return self.client.volumes.create(size=p_size, snapshot_id=p_snapId, name=p_volName)

    def deleteVolume(self, p_vol):
        return self.client.volumes.delete(p_vol)

    def getVolume(self, id):
        try:
            return self.client.volumes.get(id)
        except Exception as ex:
            logger.log.error("Cannot get volume details! %s" % str(ex))
            raise

    def getSnapshot(self, id):
        try:
            return self.client.volume_snapshots.get(id)
        except Exception as ex:
            logger.log.error("Cannot get volume details! %s" % str(ex))
            raise

    def detachVol(self, p_volId):
        vol = self.client.volumes.get(p_volId)

        try:
            vol.detach()
        except Exception as ex:
            logger.log.error("Cannot detach volume %s! %s" % (p_volId, str(ex)))
            raise

    def attachVol(self, p_volId, p_instanceId, p_mountPoint, p_hostName):
        vol = self.client.volumes.get(p_volId)
        try:
            vol.attach(p_instanceId, p_mountPoint,'rw', p_hostName)
        except Exception as ex:
            logger.log.error("Cannot attach volume %s to %s instance! %s" % (p_volId, p_instanceId, str(ex)))
            raise

class GlanceManager(object):
    """Glance module manager"""
    def __init__(self, p_sess):
        self.client = glanceClient('2', session=p_sess)

    def listImages(self, owner=None, is_public=None):
        try:
            return self.client.images.list(owner=owner, is_public=is_public)
        except Exception as ex:
            logger.log.error("Cannot list images! %s" % str(ex))
            raise

    def imageMemberList(self, member):
        try:
            return self.client.image_members.list(member=member)
        except Exception as ex:
            logger.log.error("Cannot list image members! %s" % str(ex))
            raise

    def getImage(self, id):
        try:
            return self.client.images.get(id)
        except Exception as ex:
            print str(ex)
            logger.log.error("Image does not exists in cloud service! %s" % str(ex))
            raise

    def getData(self, id):
        try:
            return self.client.images.data(id)
        except Exception as ex:
            logger.log.error("Cannot get image data! %s" % str(ex))
            raise

    def deleteImage(self, id):
        try:
            self.client.images.delete(id)
        except Exception as ex:
            logger.log.error("Cannot remove image from cloud! %s" % str(ex))
            raise

    def uploadImage(self, p_id, p_body):
        try:
            logger.log.info("Starting upload" )
            self.client.images.upload(p_id, p_body)
        except Exception as ex:
            logger.log.error("Error during upload! %s" % str(ex))
            raise

    def createImage(self, p_name):
        try:
            logger.log.info("Creating new image %s" % p_name)
            newImage = self.client.images.create(name=p_name, disk_format="raw", container_format="bare")
            return newImage
        except Exception as ex:
            logger.log.error("Cannot create image %s!" % str(ex))
            raise
