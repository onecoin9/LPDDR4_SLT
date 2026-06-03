using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Hsg.Common;

namespace Hsg.BLL
{
    public class BSRecord
    {
        //private static BSRecord _instance = new BSRecord();
        private CSVRecord _testInfoCSV;
        private string _recordName = "Record";
        public BSRecord(string fileName, string fixedTitle, bool isOverView = false)
        {
            SysConfig _config = SysConfig.GetInstance();
            string folderName = "";
            if (fileName.Length > 0)
            {
                _recordName = fileName;
            }
            String defaultPath = AppDomain.CurrentDomain.BaseDirectory + "CSV";
            if (!Directory.Exists(defaultPath))

            {
                Directory.CreateDirectory(defaultPath);
            }
            if (SystemStatus.DebugMode)
            {
                folderName = "Debug_info";
            }
            else
            {
                if (isOverView)
                {
                    folderName = "";
                }
                else
                {
                    folderName = SysConfig.MaterialNo + "@" + SysConfig.OrderNo + "\\" + SysConfig.WorkOrderNo + "[" + (SysConfig.RecordAddToTotal ? "1" : "0") + "," + (SysConfig.RecordAddToPass ? "1" : "0") + "]";
                }
            }

            string folderPath = "";
            if (_config.CSVFilePath.Value.Length > 0 && Directory.Exists(_config.CSVFilePath.Value))
            {
                folderPath = _config.CSVFilePath.Value + "\\" + folderName;
            }
            else
            {
                folderPath = defaultPath + "\\" + folderName;
            }
            if (!Directory.Exists(folderPath))

            {
                DirectoryInfo dir = Directory.CreateDirectory(folderPath);
                if (dir == null)
                {
                    return;
                }
            }
            string fullPath = Path.Combine(folderPath, fileName);
            _testInfoCSV = new CSVRecord(fullPath, fixedTitle);
        }

        public CSVRecord GetRecordObject()
        {
            return _testInfoCSV;
        }
        public void Destory()
        {
            _testInfoCSV.Destroy();
        }

    }
}
