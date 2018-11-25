from django.core.files.storage import Storage
from fdfs_client.client import Fdfs_client
from dailyfresh.settings import FAST_CLINET_CONF,FAST_URL

class FDFSStorage(Storage):
    def __init__(self,client_conf=None,base_url=None):
        if client_conf is None:
            self.client_conf = FAST_CLINET_CONF
        if base_url is None:
            self.base_url = FAST_URL

    # 打开文件的方法
    def _open(self,name, mode='rb'):
        pass

    # 保存文件方法
    def _save(self,name, content):
        client = Fdfs_client(self.client_conf)
        res = client.upload_by_buffer(content.read())
        print(res)

        '''dict {
            'Group name'      : group_name,
            'Remote file_id'  : remote_file_id,
            'Status'          : 'Upload successed.',
            'Local file name' : '',
            'Uploaded size'   : upload_size,
            'Storage IP'      : storage_ip
        }'''

        if res.get('Status') != 'Upload successed.':
            # 上传失败
            raise Exception('上传文件到fast dfs 失败')

        filename = res.get('Remote file_id')

        return filename

    def exists(self, name):
        return False

    def url(self,name):
        # 返回访问nginx_fastdfs的路径
        return self.base_url+name
