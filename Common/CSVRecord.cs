using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Hsg.Common
{
    internal class CsvValue
    {
        public UInt32 _instanceId;
        public StringBuilder _strContentBuilder;
        public StringBuilder _strFixedContentBuilder;// 用于存放固定的头部字段
        public CsvValue(UInt32 instanceId)
        {
            _instanceId = instanceId;
            _strContentBuilder = new StringBuilder();
            _strFixedContentBuilder = new StringBuilder();
        }

        public void AddRecord(string content)
        {
            string writeStr = "";
            writeStr = content.Replace(',', '|').Replace("\r\n", "").Replace("\n", "").Replace("\r", "");// 替换，避免影响csv 内容阅读
            if (_strContentBuilder.Length > 0)
            {
                _strContentBuilder.Append(",");
            }
            _strContentBuilder.Append(writeStr);
        }
        public void AddFixedContent(string content)
        {
            string writeStr = "";
            //if (content.Length == 0)
            //{
            //    return;
            //}
            writeStr = content.Replace(',', '|');// 替换，避免影响csv 内容阅读
            if (_strFixedContentBuilder.Length > 0)
            {
                _strFixedContentBuilder.Append(",");
            }
            _strFixedContentBuilder.Append(writeStr);
        }
        public void Clear()
        {
            _strContentBuilder.Clear();
            _strFixedContentBuilder.Clear();
        }
    }
    public class CSVRecord
    {
        private Dictionary<UInt32, CsvValue> _csvDict;
        private UInt32 _lastInstance;
        private StreamWriter _fileWrite;
        private Object _csvDictLock;// 避免列表多线程操作引起异常
        private string _titleString;
        public static UInt32 INVALID_INSTANCE_ID = 0; // 预留，不用来分配的
        public CSVRecord(string filePath, string title)
        {
            string fileName = Path.ChangeExtension(Path.Combine(filePath), ".csv");
            bool addTitle = false;
            _lastInstance = 0;
            _titleString = title;
            _csvDict = new Dictionary<UInt32, CsvValue>();
            _csvDictLock = new Object();
            if (!File.Exists(fileName))
            {
                addTitle = true;
            }
            try
            {
                _fileWrite = new StreamWriter(fileName, true);
            }
            catch (Exception ex)
            {
                Hlog.E("CSV", "create csv failed" + ex.Message);
            }
            if (_fileWrite != null)
            {
                _fileWrite.AutoFlush = true;
                if (addTitle && _titleString.Length > 0)
                {
                    _fileWrite.Write(_titleString);
                }
            }
        }
        public UInt32 StartOneRecord()
        {
            UInt32 instanceId = 0;
            lock (_csvDictLock)
            {
                if (_lastInstance == INVALID_INSTANCE_ID)
                {
                    _lastInstance++;
                }
                instanceId = _lastInstance;
                _lastInstance++;
                CsvValue csvItem = new CsvValue(instanceId);
                _csvDict.Add(instanceId, csvItem);
            }
            return instanceId;
        }

        private void AddContent(UInt32 itemId, string content, bool isFixed)
        {
            lock (_csvDictLock)
            {
                CsvValue csvItem;
                if (_csvDict.TryGetValue(itemId, out csvItem))
                {
                    if (isFixed)
                        csvItem.AddFixedContent(content);
                    else
                        csvItem.AddRecord(content);
                }
            }
        }

        public void AddOneRecord<T>(UInt32 itemId, T cnt)
        {
            string strContent = cnt.ToString();
            AddContent(itemId, strContent, false);
        }

        public void AddFixedRecord<T>(UInt32 itemId, T cnt)
        {
            string strContent = cnt.ToString();
            AddContent(itemId, strContent, true);
        }

        public bool CheckFileIsReady()
        {
            if(_fileWrite==null)
            {
                return false;
            }
            return true;
        }

        public void SaveRecord(UInt32 itemId, bool close)
        {
            lock (_csvDictLock)
            {
                CsvValue csvItem;
                if (_csvDict.TryGetValue(itemId, out csvItem))
                {
                    if (_fileWrite != null)
                    {
                        try
                        {
                            if (csvItem._strFixedContentBuilder.Length > 0
                               || csvItem._strContentBuilder.Length > 0)
                            {
                                _fileWrite.WriteLine();
                                if (csvItem._strFixedContentBuilder.Length > 0)
                                {
                                    _fileWrite.Write(csvItem._strFixedContentBuilder);
                                    _fileWrite.Write(",");
                                }
                                if (csvItem._strContentBuilder.Length > 0)
                                {
                                    _fileWrite.Write(csvItem._strContentBuilder);
                                }
                            }

                        }
                        catch (IOException ex)
                        {
                            Hlog.E("CSV", "Write failed:" + ex.Message);
                        }

                    }
                    csvItem.Clear();
                    if (close)
                    {
                        _csvDict.Remove(itemId);
                    }
                }
            }
        }

        public void ClearRecordBuf(UInt32 itemId)
        {
            lock (_csvDictLock)
            {
                CsvValue csvItem;
                if (_csvDict.TryGetValue(itemId, out csvItem))
                {
                    csvItem.Clear();
                }
            }
        }

        public void Destroy()
        {
            if (_fileWrite == null)
            {
                return;
            }
            lock (_csvDictLock)
            {
                _csvDict.Clear();
                _fileWrite.Close();
                _fileWrite.Dispose(); // 显式释放资源
                _fileWrite = null; // 避免重复释放
            }
        }
    }

}
