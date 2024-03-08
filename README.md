# stax
Openstack backup automation. Your openstack account password needs to be encrypted first with encrypt.py.

```
Stax 1.0 - OpenStack backup automation
Usage: stax [-ijwvebdxupsr] [InstanceId|VolumeId|BatchFile]

  -i   backup instance with volumes (detach method)
  -j   backup instance with volumes (snapshot method)
  -w   backup volume (detach method)
  -v   backup volume (snapshot method)
  -e   backup instance only
  -b   batch file (bulk uuid's)
  -d   download cloud image
  -x   delete cloud image
  -u   upload local image to cloud
  -p   pause instance
  -s   resume instance
  -r   reporting mode

Simple Crypt 1.0
Usage: encrypt.py [-edg] [Input File] [Output File]
Encrypts or decrypts requested file
  -e   encrypt file
  -d   decrypt file
  -g   use GUI for password prompt
```
