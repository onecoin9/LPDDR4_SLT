using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.IO;
using System.Reflection;
using System.Text.RegularExpressions;
namespace TBM01.old_Common
{
    class SaveAttribute : Attribute
    {
        public string ValueName { set; get; }
        public int Num;
        public SaveAttribute(string value)
        {
            ValueName = value;
            Num = 0;
        }
        public SaveAttribute(string value, int num)
        {
            ValueName = value;
            Num = num;
        }
    }


 
    public class SystemConfig
    {
        public const int PORT_NUM = 8;
        public const int TEAM_NUM = 32;//32;
        private const string CONFIG_NAME = "user_config.dat";
        static private SystemConfig _Config = new SystemConfig();
        private IOnMemberChange _onMemberChange;
        // 机台IP
        [SaveAttribute("DestIP")]
        public string DestIP { get; set; }
        // 机台端口
        [SaveAttribute("DestPort")]
        public string DestPort { get; set; }

        //Modbus slave 端口
        [SaveAttribute("MbSlavePort")]
        public string MbSlavePort { get; set; }

        //Modbus 主机端口
        [SaveAttribute("MbMasterPort")]
        public string MbMasterPort { get; set; }

        // Modbus addr
        [SaveAttribute("SlaveMbAddr")]
        public string SlaveMbAddr { get; set; }

        [SaveAttribute("MasterPorts", PORT_NUM)]
        public string[] MasterPorts { get; set; }


        [SaveAttribute("SlavePorts", PORT_NUM)]
        public string[] SlavePorts { get; set; }



        [SaveAttribute("SlaveIps", TEAM_NUM)]
        public string[] SlaveIps { get; set; }
        //是否有修改

        [SaveAttribute("DtuConfig")]
        public string DtuConfig { get; set; }

        [SaveAttribute("TestTimeout")]
        public string TestTimeout { get; set; }

        private SystemConfig()
        {
            DestIP = "127.0.0.1";
            DestPort = "7000";
            MbSlavePort = "501";
            MbMasterPort = "501";
            MasterPorts = new string[PORT_NUM];
            DtuConfig = string.Empty;
            TestTimeout = "3";
            for (int i = 0; i < PORT_NUM; i++)
            {
                MasterPorts[i] = Convert.ToString(10001 + i);
            }
            SlavePorts = new string[PORT_NUM];
            for (int i = 0; i < PORT_NUM; i++)
            {
                SlavePorts[i] = Convert.ToString(20001 + i);
            }
            SlaveMbAddr = "1";

            SlaveIps = new string[TEAM_NUM];
            for (int i = 0; i < TEAM_NUM; i++)
            {
                SlaveIps[i] = "192.168.50." + Convert.ToString(100 + i);
            }
            if (!File.Exists(CONFIG_NAME)) return;

            using (StreamReader sw = File.OpenText(CONFIG_NAME))
            {
                string str = null;

                while ((str = sw.ReadLine()) != null)
                {
                    string[] strs = str.Split('=');
                    //Regex.Matches(strs[0], @"\S\[\d+\]");
                    string name = Regex.Replace(strs[0], @"\[\d+\]", "");
                    Match index = Regex.Match(strs[0], @"\[\d+\]");
                    System.Reflection.PropertyInfo propertyInfoName = (this.GetType()).GetProperty(name);


                    if (propertyInfoName != null && str.Length > 1)
                    {
                        if (index.Length > 0) // array data.
                        {
                            Console.WriteLine("index:" + Regex.Replace(index.Value, @"\[|\]", ""));
                            string[] values = strs[1].Split(',');
                            propertyInfoName.SetValue(this, values);
                        }
                        else
                        {
                            propertyInfoName.SetValue(this, string.IsNullOrEmpty(strs[1]) ? "" : strs[1]);
                        }
                    }

                }
            }
        }

        public bool ConfigSave()
        {
            using (StreamWriter writer = File.CreateText(CONFIG_NAME))
            {
                PropertyInfo[] propertys = this.GetType().GetProperties(BindingFlags.NonPublic | BindingFlags.Public | BindingFlags.DeclaredOnly | BindingFlags.Instance);
                foreach (var v in propertys)
                {
                    SaveAttribute attr = v.GetCustomAttribute(typeof(SaveAttribute), false) as SaveAttribute;
                    if (attr != null)
                    {
                        object value = v.GetValue(this, null);

                        if (attr.Num > 0)
                        {
                            string[] valueArr = value as string[];
                            string arrayStr = string.Join(",", valueArr);
                            writer.WriteLine("{0}[{2}]={1}", v.Name, arrayStr, attr.Num);
                        }
                        else
                        {
                            writer.WriteLine("{0}={1}", v.Name, value);
                        }
                    }
                }
            }

            return false;
        }
        public static SystemConfig GetInstance()
        {
            return _Config;
        }
        /// <summary>
        /// 绑定配置修改监听
        /// </summary>
        /// <param name="onMemberChange"></param>
        public void BindMemberChangeDetect(IOnMemberChange onMemberChange)
        {
            _onMemberChange += onMemberChange;
        }
        /// <summary>
        /// 用于手动通知更新。在修改参数后，需要主动调用,通知系统参数修改
        /// </summary>
        public void UpdateSystemConfig()
        {
            if(_onMemberChange != null)
            {
                _onMemberChange();
            }
        }
    }
}
