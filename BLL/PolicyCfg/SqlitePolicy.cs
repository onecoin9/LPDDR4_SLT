using Hsg.Common.ADO;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading.Tasks;

namespace Hsg.BLL.Policy
{
    public class SqlitePolicy : PolicyBase
    {
        private const string _extName = ".db";
        //private HsgTestFile _hsgFile;
        private byte[] _cfgBytes;
        private string _description = "";
        private string _cfgName = "";
        private int _timeoutMinute;
        private UInt32 _executeFrequency;
        private SqlitePolicy(string cfgName, byte[] cfgBytes, string description, int timeout, UInt32 repeatCount)
        {
            _cfgBytes = cfgBytes;
            _description = description;
            _cfgName = cfgName;
            _timeoutMinute = timeout;
            _executeFrequency = repeatCount;
        }
        public static string GenerateFileUrl(int workOrderId)
        {
            return $"sqlite://{workOrderId}";
        }
        public static bool CheckFileName(string fileUrl)
        {
            string extName = Path.GetExtension(fileUrl);
            string pattern = @"^sqlite://\d+$";
            if (Regex.IsMatch(fileUrl, pattern))
            {
                return true;
            }
            return false;
        }
        static public SqlitePolicy LoadFile(string fileUrl)
        {
            // string input = "sqlite-work_order-123";
            string result = Regex.Match(fileUrl, @"\d+").Value;
            int workOrderId = 0;
            if (result.Length > 0 && Int32.TryParse(result, out workOrderId))
            {
                DBHandler dbHandler = DBHandler.Instance;
                string orderNo = "";
                string materialNo = "";
                string workOrderNo = "";
                byte[] testCfg = Array.Empty<byte>();
                string cfgName = "";
                byte TmpState = 0;
                int timeoutMinute = 0;
                int repeatCount = 0;
                string cfgDescription = "";
                if (dbHandler.QueryWorkOrderInfor(workOrderId, ref orderNo, ref materialNo,
                                                  ref workOrderNo, ref testCfg, ref cfgName,
                                                  ref TmpState, ref timeoutMinute, ref repeatCount, ref cfgDescription))
                {
                    if (repeatCount < 0)
                    {
                        repeatCount = 0;
                    }
                    SqlitePolicy policy = new SqlitePolicy(cfgName, testCfg, cfgDescription, timeoutMinute, (UInt32)repeatCount);
                    return policy;
                }
            }
            return null;
        }

        static public string GetFileFilter()
        {
            return "测试配置文件|*" + _extName + "*";
        }

        //public override string GetFileName()
        //{
        //    throw new NotImplementedException();
        //}

        public override bool IsEncrypt()
        {
            return false;
        }

        public override bool ReadEmiContent(ref byte[] outData)
        {
            outData = _cfgBytes;
            return true;
        }


        public override uint GetTimeout()
        {
            return (uint)_timeoutMinute;
        }
        public override UInt32 GetExecuteFrequency()
        {
            return _executeFrequency;
        }
        public override string GetExtraDetail()
        {
            return _description;
        }

        public override string GetFileName()
        {
            return _cfgName;
        }
    }
}
