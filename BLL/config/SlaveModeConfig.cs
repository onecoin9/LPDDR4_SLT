using Hsg.BLL.Policy;
using Hsg.Common;
using Newtonsoft.Json;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading.Tasks;

namespace Hsg.BLL.config
{
    public class SlaveModeConfig
    {
        //    public string WorkOrderId;
        public string WorkOrderNo { get; set; }
        public string OrderNo { get; set; }
        public string MaterialNo { get; set; }
        public int TempState { get; set; }// 0,1,2
        public int ProcessesId { get; set; }
        public string TSPath { get; set; }
        private bool CheckParamValid(ref string tsName, ref string errorMsg)
        {
            if (WorkOrderNo == null || WorkOrderNo.Length == 0)
            {
                errorMsg = "WorkOrderNo invalid";
                return false;
            }
            if (OrderNo == null || OrderNo.Length == 0)
            {
                errorMsg = "OrderNo invalid";
                return false;
            }
            if (MaterialNo == null || MaterialNo.Length == 0)
            {
                errorMsg = "MaterialNo invalid";
                return false;
            }
            if (TempState < 0 || TempState >= (int) Hsg.Common.TempState.TmpMax) // 温控设置
            {
                errorMsg = "TempState invalid";
                return false;
            }
            if (TempState == 2)
            {
                errorMsg = "Platform not support Low temperature";
                return false;
            }
            if (ProcessesId < 0 || ProcessesId >= 3) // 工序编号
            {
                errorMsg = "ProcessesId invalid";
                return false;
            }
            if (TSPath == null || TSPath.Length == 0)
            {
                errorMsg = "TSPath invalid";
                return false;
            }
            else
            {
                //if(Path.GetExtension(TSPath) == SysConfig.PolicyFileExtName)
                //{
                //    TSPath = TSPath.Substring(0,TSPath.Length - SysConfig.PolicyFileExtName.Length);
                //}
              //  string filePath = SysConfig.GetPolicyFileFullPath(TSPath);
                PolicyFile file = PolicyFile.Deserialize(TSPath, ref errorMsg);
                if (file == null) //
                {
                    return false;
                }
                tsName = TSPath;
            }
            return true;
        }
        public static SlaveModeConfig LoadConfig(string filePath, ref string tsName, ref string errorMsg)
        {
            if (File.Exists(filePath))
            {
                using (StreamReader reader = new StreamReader(filePath))
                {
                    //SlaveModeConfig test = new SlaveModeConfig();
                    //test.MaterialNo = "1";
                    //test.OrderNo = "2";
                    //test.ProcessesId = 1;
                    //test.TempState = 0;
                    //test.TSPath = "Config\\6771-6G.ts";
                    //test.WorkOrderNo = "123456";
                    //string testJson = JsonConvert.SerializeObject(test);
                    SlaveModeConfig parsedObject = null;
                    try
                    {
                        string content = reader.ReadToEnd();
                        // string stringWithoutNewlines = Regex.Replace(content, @"\r\n|\r|\n|\t", "");
                        parsedObject = (SlaveModeConfig)JsonConvert.DeserializeObject<SlaveModeConfig>(content);
                        if (!parsedObject.CheckParamValid(ref tsName, ref errorMsg))
                        {
                            return null;
                        }
                    }
                    catch(Exception ex)
                    {
                        errorMsg = "config file format error:" + ex.Message;
                        return null;
                    }
                    return parsedObject;
                }
            }
            return null;
        }
    }
}
