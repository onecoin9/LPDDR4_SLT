using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Hsg.BLL.Policy
{
    internal class CommonPolicy : PolicyCfgBase
    {
        private const string _extName = ".cfg";
        private byte[] _emiContent; // emi 内容
        private CommonPolicy() { }
        static public CommonPolicy LoadFile(string filePath)
        {
            if (File.Exists(filePath))
            {
                using (Stream stream = File.OpenRead(filePath))
                {
                    if (stream.Length > 0)
                    {
                        CommonPolicy policy = new CommonPolicy();
                        policy._fileName = Path.GetFileName(filePath);
                        policy._emiContent = new byte[stream.Length + 1];
                        stream.Read(policy._emiContent, 0, (int)stream.Length);
                        return policy;
                    }
                }
            }
            return null;
        }

        static public CommonPolicy LoadFile(byte[] fileBytes, string fileName )
        {
            using (MemoryStream stream = new MemoryStream(fileBytes))
            {
                if (stream.Length > 0)
                {
                    CommonPolicy policy = new CommonPolicy();
                    policy._fileName = fileName;
                    policy._emiContent = fileBytes;
                    return policy;
                }
            }
            return null;
        }

        public static bool CheckFileName(string filePath)
        {
            string extName = Path.GetExtension(filePath);
            if (extName == _extName)
            {
                return true;
            }
            return false;
        }


        static public string GetFileFilter()
        {
            return "配置文件|*" + _extName + "*";
        }

        static public string GetExtName()
        {
            return _extName;
        }

        public override bool IsEncrypt()
        {
            return false;
        }

        public override bool ReadEmiContent(ref byte[] outData)
        {
            //using (var fs = File.OpenRead())
            //{
            //    byte[] readBuf = new byte[fs.Length + 1];// 多一个字节用来做结束，避免测试板出现异常
            //    if (fs.Read(readBuf, 0, readBuf.Length - 1) == fs.Length)
            //    {
            //        outData = readBuf;
            //        return true;
            //    }
            //}
            if(_emiContent!= null && _emiContent.Length > 0)
            {
                outData = _emiContent;
            }
            return false;
        }
    }
}
