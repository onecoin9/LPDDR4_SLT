using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.IO;
using System.Text.RegularExpressions;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Xml.Linq;
using System.Security.Policy;
using Hsg.Common;
using Hsg.BLL.Policy;

namespace Hsg.BLL
{
    /// <summary>
    /// 用于标记是否有成员发生改变
    /// </summary>
    public delegate void IOnMemberChange();
    public delegate void IOnMembersChange(UInt32 param);
    /// <summary>
    /// 用于配置修改完成，通知所有引用的对象更新信息
    /// </summary>
    public delegate void IOnUpdateConfig();
    /// <summary>
    /// 用于通知对象引用的配置修改了需要更新
    /// </summary>
    public delegate void IOnConfigChange();

    public class ConfigString
    {
        private IOnMemberChange _onMemberChange;
        private string _name;
        public string Name
        {
            get { return _name; }
        }
        protected string _value;
        public virtual string Value
        {
            get
            {
                return _value;
            }
            set
            {
                if (_value != value)
                {
                    _value = value;
                    OnValueChange();
                }
            }
        }
        protected void OnValueChange()
        {
            if (_onMemberChange != null)
            {
                _onMemberChange();
            }
        }
        public bool CheckBoolValue()
        {
            if (_value == "1")
            {
                return true;
            }
            return false;
        }
        public void SetTrue()
        {
            Value = "1";
        }
        public void SetFalse()
        {
            Value = "0";
        }

        public ConfigString(String name)
        {
            _name = name;
            _value = "";
        }


        public void DetectOnValueChange(IOnMemberChange onValueChange)
        {
            _onMemberChange += onValueChange;
        }
        public override string ToString()
        {
            string outString = _name + "=" + _value;
            return outString;
        }

        public bool LoadFromString(string source)
        {
            string[] attr = source.Split('=');
            if (attr.Count() == 2)
            {
                _name = attr[0];
                _value = attr[1];
                return true;
            }
            return false;
        }
    }

    public class ConfigStringList
    {
        private ConfigString[] _attrList;
        private int _listNum = 0;
        public int GetCount()
        {
            return _listNum;
        }
        public ConfigStringList(string name, int listNum)
        {
            _attrList = new ConfigString[listNum];
            for (int i = 1; i <= listNum; i++)
            {
                if (listNum > 10 && listNum <= 99)
                {
                    _attrList[i - 1] = new ConfigString(name + i.ToString("D2"));
                }
                else
                {
                    _attrList[i - 1] = new ConfigString(name + i);
                }

            }
            _listNum = listNum;
        }
        /// <summary>
        /// bind for id change
        /// </summary>
        /// <param name="onMemberChanged"></param>
        /// <param name="id"></param>
        public void BindOnMemberChange(IOnMemberChange onMemberChanged, int id)
        {
            if (onMemberChanged == null)
            {
                return;
            }
            if (id >= 0 && id < _listNum)
            {
                _attrList[id].DetectOnValueChange(onMemberChanged);
            }
        }
        public String GetItemValue(int index)
        {
            if (index < 0 || index >= _listNum)
            {
                return null;
            }
            return _attrList[index].Value;
        }
        public string ItemToString(int index)
        {
            return _attrList[index].ToString();
        }
        public void SetItem(int index, string setValue)
        {
            if (index < 0 || index >= _listNum)
            {
                return;
            }
            _attrList[index].Value = setValue;
        }
    }

    public class PathConfigString : ConfigString
    {
        public new String Value
        {
            get
            {
                if (!Path.IsPathRooted(_value))
                {
                    return AppDomain.CurrentDomain.BaseDirectory + _value;
                }
                else
                {
                    return _value;
                }
            }
            set
            {
                int rootLen = AppDomain.CurrentDomain.BaseDirectory.Length;

                if (value.Length >= rootLen && value.StartsWith(AppDomain.CurrentDomain.BaseDirectory))
                {
                    _value = GetRelativePath(AppDomain.CurrentDomain.BaseDirectory, value);
                }
                else
                {
                    _value = value;
                }
                OnValueChange();
            }
        }
        private string GetRelativePath(string basePath, string targetPath)
        {
            Uri baseUri = new Uri(basePath);
            Uri targetUri = new Uri(targetPath);

            Uri relativeUri = baseUri.MakeRelativeUri(targetUri);
            string relativePath = Uri.UnescapeDataString(relativeUri.ToString());
            return relativePath.Replace('/', '\\');
        }
        public PathConfigString(string name) : base(name)
        {
        }
    }

    public class SysConfig
    {
        public const int PORT_NUM = 12;
        public const int DEV_NUM = 50;// 这里是相对机台来说，有多少个目标测试组。
        public const int TEAM_GROUP_NUM = 2; // 采用的拼板方式。这里是采用两块通讯板
        public static readonly int REPEAT_COUNT_INVALID = 0;
        private string CONFIG_NAME = "config.ini";
        private const string DEBUG_CONFIG_NAME = "debug_config.ini";
        private const string USER_LOCAL_FOLDER = "C:\\MT02Config";// 设置了一个本地C目录下配置文件，方便MES调用
        //  public static bool debug_flag = false;
        public static string PolicyFolderPath = "Policy";// 配方、方案文件夹
        public static string PolicyFileExtName = ".tpf";//配方后缀
        public static string PolicyFileFilter = "测试配置文件|*.tpf*";//配方后缀
        public static WorkMode WorkMode { get; private set; } // 工作模式
        public static int WorkOrderId { get; private set; } // 工单ID，或者母单ID
        public static string WorkStageDescription { get; private set; } // 工序描述
        public static string WorkStageName { get; private set; } // 工序名称
        public static string WorkOrderNo { get; private set; }// 工单号
        public static string OrderNo { get; private set; }// 订单号
        public static string MaterialNo { get; private set; }// 物料号
        public static byte TempState { get; private set; }// 温控要求
        public static bool RecordAddToTotal { get; private set; }// 测试记录加入到总数
        public static bool RecordAddToPass { get; private set; }// 测试记录加入到pass
 //       public static UInt32 ExecuteFrequency { get; set; }// 运行时 测试执行次数测试，如果配置文件有优先使用，否则使用上位机设置的 0 表示默认未设置执行一次
      //  public static bool LockExecuteFrequency { get; set; }// 锁定一次测试执行的次数，避免无效的设置
        private static string PolicyFilePath;// 测试配置文件路径,适用于 从机模式，外部设置
        public static void SetWorkOrderDetail(WorkMode workMode, string workStageDescription, string workStageName,
            int workOrderId = 0, string workOrderNo = "", string orderNo = "",
            string materialNo = "", byte tempState = 0,
            bool addTotal = false, bool addPass = false, string policyFile = "")
        {
            WorkMode = workMode;
            WorkStageDescription = workStageDescription;
            WorkStageName = workStageName;
            WorkOrderId = workOrderId;
            WorkOrderNo = workOrderNo;
            OrderNo = orderNo;
            MaterialNo = materialNo;
            TempState = tempState;
            RecordAddToPass = addPass;
            RecordAddToTotal = addTotal;
            PolicyFilePath = policyFile;
        }
        /// <summary>
        /// 获取配置路径
        /// </summary>
        public string TestPolicyPath
        {
            get
            {
                switch (WorkMode)
                {
                    case Common.WorkMode.Debug:
                        return DebugPolicyConfig.Value;
                    case Common.WorkMode.Online:
                        return "SQL_";
                    case Common.WorkMode.Slave:
                        return PolicyFilePath;
                    case Common.WorkMode.OffLine:
                        return PolicyFilePath/*SqlitePolicy.GenerateFileUrl(WorkOrderId)*/;
                    default:
                        return "";
                }
            }
        }
        private static object _classLock = new object();
        private static SysConfig _config;
        public IOnUpdateConfig OnConfigUpdate;
        /// <summary>
        /// 控制机台的地址和TCP端口
        /// </summary>
        public ConfigString DestIp { get; set; }
        public ConfigString DestPort { get; set; }
        /// <summary>
        /// 回传给 Handler 时，主动连接的目标端口（JSON 上报通道）
        /// </summary>
        public ConfigString HandlerReplyPort { get; set; }
        /// <summary>
        /// MBUS 相关设置
        /// </summary>
        public ConfigString MbSlaveAddr { get; set; }
        public ConfigString MbTxPort { get; set; }
        public ConfigString MbRxPort { get; set; }
        /// <summary>
        /// UDP端口
        /// </summary>
        /// <returns></returns>
        public ConfigStringList TxPort { get; set; }
        public ConfigStringList RxPort { get; set; }
        /// <summary>
        /// 通讯板地址A组
        /// </summary>
        /// <returns></returns>
        public ConfigStringList GroupAIp { get; set; }
        /// <summary>
        /// 通讯板地址A组
        /// </summary>
        /// <returns></returns>
        public ConfigStringList GroupBIp { get; set; }
        /// <summary>
        /// 测试超时时间
        /// </summary>
       //public ConfigString Timeout { get; set; }
        /// <summary>
        /// 配置文件路径，emi/policy path
        /// </summary>
        public ConfigString DebugPolicyConfig { get; set; }
        /// <summary>
        /// 控制IO
        /// </summary>
        public ConfigString IOCtrAId { get; set; }
        /// <summary>
        /// 启动时间（上电后）
        /// </summary>
        public ConfigString IOCtrAStart { get; set; }
        /// <summary>
        /// IO持续运行时间
        /// </summary>
        public ConfigString IOCtrASpan { get; set; }
        /// <summary>
        /// 分几次控制IO
        /// </summary>
        public ConfigString IOCtrBatch { get; set; }

        public ConfigString ConfigVersion { get; set; }
        /// <summary>
        /// 可以编辑软件标题
        /// </summary>
        public ConfigString ExeTitle { get; set; }

        /// <summary>
        /// 可以设置dut 顺序0，表示从左到右，1表示从右到左
        /// </summary>
        public ConfigString DutOrder { get; set; }
        /// <summary>
        /// 从左到右
        /// </summary>
        public const int DUT_ORDER_LEFT_TO_RIGHT = 0;
        /// <summary>
        /// 从右到左
        /// </summary>
        public const int DUT_ORDER_RIGHT_TO_LEFT = 1;

        /// <summary>
        /// CSV detail 文件标题
        /// </summary>
        public ConfigString CSVDetailTitle { get; set; }

        /// <summary>
        /// CSV record 文件标题
        /// </summary>
        public ConfigString CSVRecordTitle { get; set; }

        /// <summary>
        /// CSV 文件标题 汇总文件
        /// </summary>
        public ConfigString OverviewTitle { get; set; }
        /// <summary>
        /// CSV 文件保存路径
        /// </summary>
        public PathConfigString CSVFilePath { get; set; }
        //   public const string BOARD_PROTOCOL_QM = "乾明9708/9701B";
        public const string BOARD_PROTOCOL_AC = "ACROVIEW";
        /// <summary>
        /// 通讯板协议类型 (HXY,QM_9708)
        /// </summary>
        public ConfigString BoardProtocol { get; set; }
        /// <summary>
        /// 测试板连接超时(S)
        /// </summary>
        public ConfigString DutConnectTimeout { get; set; }
        /// <summary>
        /// 等待测试组就绪超时时间(S)
        /// </summary>
        public ConfigString TeamWaitReadyTimeout { get; set; }
        /// <summary>
        /// 异常等待时间(S)
        /// </summary>
        public ConfigString AbnormalWaitSecond { get; set; }

        /// <summary>
        /// 使用源码测试方案(0,1) 0 代表不使用加密的测试方案
        /// </summary>
        //public ConfigString EncryptionPolicy { get; set; }

        /// <summary>
        /// 测试板广播地址
        /// </summary>
        public const string BroadcastAddrForBoard = "192.168.50.255";
        /// <summary>
        /// 通讯板接收端口
        /// </summary>
        public const ushort BroadcastPortForBoard = 60000;

        /// <summary>
        ///  四个 bin 的分bin 码
        /// </summary>
        public ConfigStringList CodeToBin { get; set; }
        public const int MAX_BIN_COUNT = 4;
        public ConfigString DefaultBin { get; set; }

        public ConfigString HightTempSupport { get; set; }
        public ConfigString LowTempSupport { get; set; }
        public ConfigString HightTempValue { get; set; }
        public ConfigString LowTempValue { get; set; }
        public ConfigString NormalTempHight { get; set; }
        /// <summary>
        /// 常温检查
        /// </summary>
        public ConfigString NormalTempCheck { get; set; }
        // public ConfigString TempControlEnable { get; set; }
        public ConfigString HightTempWaitTimeout { get; set; }
        public ConfigString NormalTempWaitTimeout { get; set; }
        public ConfigString TempMistake { get; set; }
        public ConfigString TempReparation { get; set; }
        public ConfigString FanPowerPrecent { get; set; }
        public ConfigString FanLowSpeed { get; set; }
        private const int TEMP_SVR_PORT_MAX_NUM = 3;
        public ConfigStringList TempSvrPorts { get; set; }
        public ConfigStringList TempSvrAddr { get; set; }
        /// <summary>
        /// 温度使用差异补偿
        /// </summary>
        public ConfigString UseDiffReparation { get; set; }
        /// <summary>
        /// 温度差异补偿记录
        /// </summary>
        public ConfigStringList SiteTempReparation { get; set; }
        /// <summary>
        /// 输出给通讯板的工作电压
        /// </summary>
        public ConfigString WorkVoltage { get; set; }
        /// <summary>
        /// 输出给通讯板的工作电压关闭判定阈值
        /// </summary>
        public ConfigString VoltageCloseThreshold { get; set; }

        /// <summary>
        /// 0~3  E,W,I,D
        /// </summary>
        public ConfigString LogLevel { get; set; }
        /// <summary>
        /// 设置每一批次dut 启动的上电间隔
        /// </summary>
        public ConfigString DutsIOSetIntervalSec { get; set; }
        /// <summary>
        /// 两组测试板执行间隔
        /// </summary>
        public ConfigString TeamExecTmSpan { get; set; }
        /// <summary>
        /// 调试模式，自动重新启动
        /// </summary>
       // public ConfigString DebugAutoRetry { get; set; }
        /// <summary>
        /// 调试模式 用于验板
        /// </summary>
        public ConfigString DebugBoardTest { get; set; }
        /// <summary>
        /// mes server 信息
        /// </summary>
        public ConfigString MesServiceAddr { get; set; }
        public ConfigString MesServicePort { get; set; }
        // ContinuousFreq 加严复测次数
     //   public ConfigString ContinuousFreq { get; set; }
        /// <summary>
        /// 加严失败的最大次数
        /// </summary>
      //  public ConfigString RetryMaxFailCount { get; set; }
        /// <summary>
        /// 重测结果优化，如果测试总次数达到要求，且没有结果错误，仅有环境异常，认定为ok
        /// </summary>
       // public ConfigString RetryResultOptimization { get; set; }
	   public ConfigString RepeatIntervalSec { get; set; }
        /// <summary>
        /// 测试板反馈的环境异常码，当做环境异常处理
        /// </summary>
        public ConfigString TestboardEvCode { get; set; }

        /// <summary>
        /// 验机模式
        /// </summary>
        public ConfigString DiagnosticMode { get; set; }
        /// <summary>
        /// 初始高温全开
        /// </summary>
        public ConfigString TempCtrInitAllEnable { get; set; }

        /// <summary>
        /// 待机保持通讯板上电
        /// </summary>
        public ConfigString IdlePowerHold { get; set; }
        /// <summary>
        /// 按照测试段分BIN
        /// </summary>
        public ConfigString OrderBinByStage { get; set; }
        private SysConfig()
        {
            int configCount = 0;
            if(!Directory.Exists(USER_LOCAL_FOLDER))
            {
                Directory.CreateDirectory(USER_LOCAL_FOLDER);
            }
            if (WorkMode == Common.WorkMode.Debug)
            {
                CONFIG_NAME = DEBUG_CONFIG_NAME;
            }
            string local_root_path = Path.Combine(USER_LOCAL_FOLDER, CONFIG_NAME);
            if (File.Exists(local_root_path))
            {
                CONFIG_NAME = local_root_path;
            }
            DestIp = new ConfigString("DestIp") { Value = "127.0.0.1" };
            DestPort = new ConfigString("DestPort") { Value = "7000" };
            HandlerReplyPort = new ConfigString("HandlerReplyPort") { Value = "64100" };

            MbSlaveAddr = new ConfigString("MbSlaveAddr") { Value = "1" };
            MbRxPort = new ConfigString("MbRxPort") { Value = "501" };
            MbTxPort = new ConfigString("MbTxPort") { Value = "501" };

            TxPort = new ConfigStringList("TxPort", PORT_NUM);
            RxPort = new ConfigStringList("RxPort", PORT_NUM);

 //           Timeout = new ConfigString("Timeout") { Value = "10" };
            DebugPolicyConfig = new ConfigString(nameof(DebugPolicyConfig));

            IOCtrAId = new ConfigString("IOCtrAId") { Value = ((UInt32)(EIOGroup.SWITCH_GROUP_INVALID)).ToString() };
            IOCtrAStart = new ConfigString("IOCtrAStart") { Value = "1" };
            IOCtrASpan = new ConfigString("IOCtrASpan") { Value = "6" };
            IOCtrBatch = new ConfigString(nameof(IOCtrBatch)) { Value = "4" };
            ConfigVersion = new ConfigString(nameof(ConfigVersion)) { Value = "0" };
            ExeTitle = new ConfigString(nameof(ExeTitle)) { Value = "昂科电子测试控制系统" };
            DutOrder = new ConfigString(nameof(DutOrder)) { Value = "0" };
			CSVRecordTitle = new ConfigString(nameof(CSVRecordTitle)) { Value = "TaskSerialNo,StartTime,EndTime,Duration,TesterId,BoardId,DutId,BinNumber,Result,StateCode,StageCount,Stage1,Stage1Result,Duration1,Stage2,Stage2Result,Duration2,Stage3,Stage3Result,Duration3" };
            CSVDetailTitle = new ConfigString(nameof(CSVDetailTitle)) { Value = "TaskSerialNo,StartTime,Timestamp,Duration,TesterId,BoardId,DutId,TBVersion,Temp,BinCode,Result,StateCode,Detail,StageInfo,ExcuteCount"};	
 
            OverviewTitle = new ConfigString(nameof(OverviewTitle)) { Value = "Start,Duration,Material,Order,WorkOrder,Bin1,Bin2,Bin3,Bin4,Total,Bin1Precent,WorkStage,Temp,Policy,ConfigNum,Config1File,Config1Param,FailCount1,Config2File,Config2Param,FailCount2,Config3File,Config3Param,FailCount3" };
            CSVFilePath = new PathConfigString(nameof(CSVFilePath)) { Value = "CSV" };
            BoardProtocol = new ConfigString(nameof(BoardProtocol)) { Value = BOARD_PROTOCOL_AC };
            DutConnectTimeout = new ConfigString(nameof(DutConnectTimeout)) { Value = "10" };
            TeamWaitReadyTimeout = new ConfigString(nameof(TeamWaitReadyTimeout)) { Value = "45" };
            AbnormalWaitSecond = new ConfigString(nameof(AbnormalWaitSecond)) { Value = "60" };
           // EncryptionPolicy = new ConfigString(nameof(EncryptionPolicy)) { Value = "1" };
            DefaultBin = new ConfigString(nameof(DefaultBin)) { Value = "4" };
            HightTempSupport = new ConfigString(nameof(HightTempSupport)) { Value = "1" };
            LowTempSupport = new ConfigString(nameof(LowTempSupport)) { Value = "0" };
            HightTempValue = new ConfigString(nameof(HightTempValue)) { Value = "85" };
            NormalTempHight = new ConfigString(nameof(NormalTempHight)) { Value = "35" };
            NormalTempCheck = new ConfigString(nameof(NormalTempCheck)) { Value = "1" };
            // TempControlEnable = new ConfigString(nameof(TempControlEnable)) { Value = "0" };
            HightTempWaitTimeout = new ConfigString(nameof(HightTempWaitTimeout)) { Value = "35" };
            NormalTempWaitTimeout = new ConfigString(nameof(NormalTempWaitTimeout)) { Value = "180" };
            TempMistake = new ConfigString(nameof(TempMistake)) { Value = "5" };
            TempReparation = new ConfigString(nameof(TempReparation)) { Value = "5" };
            FanPowerPrecent = new ConfigString(nameof(FanPowerPrecent)) { Value = "50" };
            FanLowSpeed = new ConfigString(nameof(FanLowSpeed)) { Value = "2000" };
            LowTempValue = new ConfigString(nameof(LowTempValue)) { Value = "0" };
            LogLevel = new ConfigString(nameof(LogLevel)) { Value = "3" };//0~3
            DutsIOSetIntervalSec = new ConfigString(nameof(DutsIOSetIntervalSec)) { Value = "1" };
            TeamExecTmSpan = new ConfigString(nameof(TeamExecTmSpan)) { Value = "5000" };
          //  DebugAutoRetry = new ConfigString(nameof(DebugAutoRetry)) { Value = "0" };
            DebugBoardTest = new ConfigString(nameof(DebugBoardTest)) { Value = "0" };

            TempSvrPorts = new ConfigStringList(nameof(TempSvrPorts), TEMP_SVR_PORT_MAX_NUM);

            MesServiceAddr = new ConfigString(nameof(MesServiceAddr)) { Value = "127.0.0.1" };
            MesServicePort = new ConfigString(nameof(MesServicePort)) { Value = "9900" };
            RepeatIntervalSec = new ConfigString(nameof(RepeatIntervalSec)) { Value = "1" };
            UseDiffReparation = new ConfigString(nameof(UseDiffReparation)) { Value = "0" };
          //  ContinuousFreq = new ConfigString(nameof(ContinuousFreq)) { Value = "0" };
           // RetryMaxFailCount = new ConfigString(nameof(RetryMaxFailCount)) { Value = "1" };
            TestboardEvCode = new ConfigString(nameof(TestboardEvCode)) { Value = "55,37,03" };
            WorkVoltage = new ConfigString(nameof(WorkVoltage)) { Value = "5.45" };
            VoltageCloseThreshold = new ConfigString(nameof(VoltageCloseThreshold)) { Value = "0.5" };
            DiagnosticMode = new ConfigString(nameof(DiagnosticMode)) { Value = "0" };
            TempCtrInitAllEnable = new ConfigString(nameof(TempCtrInitAllEnable)) { Value = "0" };
            IdlePowerHold = new ConfigString(nameof(IdlePowerHold)) { Value = "0" };
            OrderBinByStage = new ConfigString(nameof(OrderBinByStage)) { Value = "0" };
            
            for (int i = 0; i < PORT_NUM; i++)
            {
                TxPort.SetItem(i, Convert.ToString(2001 + i));
            }
            for (int i = 0; i < PORT_NUM; i++)
            {
                RxPort.SetItem(i, Convert.ToString(2001 + i));
            }
            for (int i = 0; i < TEMP_SVR_PORT_MAX_NUM; i++)
            {
                TempSvrPorts.SetItem(i, Convert.ToString(64201 + i));
            }
            GroupAIp = new ConfigStringList(nameof(GroupAIp), DEV_NUM);
            for (int i = 0; i < DEV_NUM; i++)
            {
                GroupAIp.SetItem(i, "192.168.50." + Convert.ToString(100 + i));
            }

            GroupBIp = new ConfigStringList("GroupBIp", DEV_NUM);
            for (int i = 0; i < DEV_NUM; i++)
            {
                GroupBIp.SetItem(i, "192.168.50." + Convert.ToString(200 + i));
            }
            TempSvrAddr = new ConfigStringList(nameof(TempSvrAddr), DEV_NUM);
            for (int i = 0; i < DEV_NUM; i++)
            {
                TempSvrAddr.SetItem(i, "192.168.50." + Convert.ToString(2 + i));
            }
            SiteTempReparation = new ConfigStringList(nameof(SiteTempReparation), DEV_NUM);
            for (int i = 0; i < DEV_NUM; i++)
            {
                SiteTempReparation.SetItem(i, "");
            }
            CodeToBin = new ConfigStringList(nameof(CodeToBin), 4);
            CodeToBin.SetItem(0, "2");
            CodeToBin.SetItem(1, "3,7");// FALI
            CodeToBin.SetItem(2, "6,8,9");
            //SelectDev = new ConfigStringList("SelectDev", DEV_NUM);
            //for (int i = 0; i < DEV_NUM; i++)
            //{
            //    SelectDev.SetItem(i, "1");
            //}

            if (!File.Exists(CONFIG_NAME))
            {
                ConfigSave();
                return;
            }

            using (StreamReader swReader = File.OpenText(CONFIG_NAME))
            {
                string str = null;

                while ((str = swReader.ReadLine()) != null)
                {
                    ConfigString configAttr = new ConfigString("");
                    if (configAttr.LoadFromString(str))
                    {
                        configCount++;
                        string name = Regex.Replace(configAttr.Name, @"\d+$", "");  // 只替换末尾的数字
                        Match index = Regex.Match(configAttr.Name, @"\d+$");        // 只匹配末尾的数字
                        PropertyInfo info = (this.GetType()).GetProperty(name);
                        if (info != null && configAttr.Name.Length > 1)
                        {
                            if (info.PropertyType == typeof(ConfigStringList))
                            {
                                MethodInfo method = typeof(ConfigStringList).GetMethod("SetItem");
                                object[] param = new object[2] { (object)(int.Parse(index.Value) - 1), (object)configAttr.Value };
                                method.Invoke(info.GetValue(this), param);
                            }
                            else if (info.PropertyType == typeof(ConfigString))
                            {
                                info.SetValue(this, configAttr);
                            }
                            else if (info.PropertyType == typeof(PathConfigString))
                            {
                                PathConfigString config = new PathConfigString(configAttr.Name);
                                config.Value = configAttr.Value;
                                info.SetValue(this, config);
                            }
                        }
                    }
                }
            }

            if (configCount != EnumConfigCount())
            {
                ConfigSave();
            }
        }
        private int EnumConfigCount()
        {
            int count = 0;
            FieldInfo[] attrs = this.GetType().GetFields(BindingFlags.NonPublic | BindingFlags.Public | BindingFlags.DeclaredOnly | BindingFlags.Instance);
            foreach (FieldInfo v in attrs)
            {
                if (v.FieldType == typeof(ConfigString) || v.FieldType == typeof(PathConfigString))
                {
                    count++;
                }
                else if (v.FieldType == typeof(ConfigStringList))
                {
                    ConfigStringList attrList = v.GetValue(this) as ConfigStringList;
                    count += attrList.GetCount();
                }
            }
            return count;
        }
        public bool ConfigSave()
        {
            using (StreamWriter writer = File.CreateText(CONFIG_NAME))
            {
                // PropertyInfo[] propertys = this.GetType().GetProperties(BindingFlags.NonPublic | BindingFlags.Public | BindingFlags.DeclaredOnly | BindingFlags.Instance);
                FieldInfo[] attrs = this.GetType().GetFields(BindingFlags.NonPublic | BindingFlags.Public | BindingFlags.DeclaredOnly | BindingFlags.Instance);
                foreach (FieldInfo v in attrs)
                {
                    if (v.FieldType == typeof(ConfigString) || v.FieldType == typeof(PathConfigString))
                    {
                        ConfigString attr = v.GetValue(this) as ConfigString;
                        writer.WriteLine(attr.ToString());
                    }
                    else if (v.FieldType == typeof(ConfigStringList))
                    {
                        ConfigStringList attrList = v.GetValue(this) as ConfigStringList;
                        for (int i = 0; i < attrList.GetCount(); i++)
                        {
                            writer.WriteLine(attrList.ItemToString(i));
                        }
                    }
                }
            }

            return false;
        }
        public static SysConfig GetInstance()
        {
            if (_config == null)
            {
                lock (_classLock)
                {
                    if (_config == null)
                    {
                        _config = new SysConfig();
                    }
                }
            }
            return _config;
        }
        /// <summary>
        /// 通知调用配置的对象，配置信息修改完成，使用最新配置信息
        /// </summary>
        public void ChangeConfigEnd()
        {
            ConfigVersion.Value = (Int32.Parse(ConfigVersion.Value) + 1).ToString();
            if (OnConfigUpdate != null)
            {
                OnConfigUpdate();
            }
            ConfigSave();
        }
        /// <summary>
        /// 通过地址查询 IP 索引，  groupA  为0~DEV_NUM-1 groupB 为 DEV_NUM ~ 2DEV_NUM-1
        /// </summary>
        /// <param name="ip"></param>
        /// <returns></returns>
        public int GetIpIndex(string ip)
        {
            for (int i = 0; i < GroupAIp.GetCount(); i++)
            {
                if (GroupAIp.GetItemValue(i) == ip)
                {
                    return i;
                }
            }
            for (int i = 0; i < GroupBIp.GetCount(); i++)
            {
                if (GroupBIp.GetItemValue(i) == ip)
                {
                    return i + DEV_NUM;
                }
            }
            return -1;
        }

        public int GetIpIndex(int teamId, int groupId)
        {
            return groupId * DEV_NUM + teamId;
        }

        public ushort[] GetTempSvrPorts()
        {
            ushort[] temp = new ushort[TEMP_SVR_PORT_MAX_NUM];
            int valueCount = 0;
            for (int i = 0; i < TempSvrPorts.GetCount(); i++)
            {
                string value = TempSvrPorts.GetItemValue(i);
                UInt16 uPort = 0;
                if (ushort.TryParse(value, out uPort))
                {
                    temp[valueCount] = uPort;
                    valueCount++;
                }
            }
            if (valueCount != TEMP_SVR_PORT_MAX_NUM)
            {
                ushort[] ret = Array.Empty<ushort>();
                if (valueCount > 0)
                {
                    ret = new ushort[valueCount];
                    Array.Copy(temp, ret, valueCount);
                }
                return ret;
            }
            return temp;
        }
		
 		private List<string> GetFilesWithExtensions(string folderPath, string[] fileExtensions)
        {
            List<string> files = new List<string>();
            try
            {
                foreach (string ext in fileExtensions)
                {
                    // 获取指定文件夹及其子文件夹中的所有指定后缀的文件
                    string[] foundFiles = Directory.GetFiles(folderPath, "*" + ext, SearchOption.AllDirectories);
                    foreach (var v in foundFiles)
                    {
                        files.Add(Path.GetFileNameWithoutExtension(v));
                    }

                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"发生错误：{ex.Message}");
            }
            return files;
        }
        public string[] GetPolicyFileNameList()
        {
            string[] fileExtensions = new string[] { PolicyFileExtName };
            List<string> nameList = GetFilesWithExtensions(PolicyFolderPath, fileExtensions);
            return nameList.ToArray();
        }
        static public string GetPolicyFileFullPath(string fileName)
        {
            return Path.Combine(SysConfig.PolicyFolderPath, fileName) + SysConfig.PolicyFileExtName;
        }
    }

    public class UdpConfig
    {
        //private int _ipIndex;
        private int _portIndex;
        private SysConfig _sysConfig;
        private bool _bConfigChange;
        private IOnMemberChange _onConfigChange;
        //public string IP
        //{
        //    get { return _sysConfig.DevIp.GetItemValue(_ipIndex); }
        //}
        public string TxPort
        {
            get { return _sysConfig.TxPort.GetItemValue(_portIndex); }
        }
        public string RxPort
        {
            get { return _sysConfig.RxPort.GetItemValue(_portIndex); }
        }
        public UdpConfig(int portIndex, IOnMemberChange onConfigChange)
        {
            // _ipIndex = ipIndex;
            _sysConfig = SysConfig.GetInstance();
            // _sysConfig.DevIp.BindOnMemberChange(OnMemberChange, ipIndex);
            if (_sysConfig.DutOrder.Value == SysConfig.DUT_ORDER_RIGHT_TO_LEFT.ToString())
            {
                portIndex = SysConfig.PORT_NUM - portIndex - 1;
            }

            _portIndex = portIndex;
            _sysConfig.TxPort.BindOnMemberChange(OnMemberChange, portIndex);
            _sysConfig.RxPort.BindOnMemberChange(OnMemberChange, portIndex);
            _sysConfig.OnConfigUpdate += NotifyConfigUpdate;
            _onConfigChange = onConfigChange;
        }
        private void OnMemberChange()
        {
            _bConfigChange = true;
        }
        /// <summary>
        /// 通知配置信息修改
        /// </summary>
        private void NotifyConfigUpdate()
        {
            if (_onConfigChange != null && _bConfigChange)
            {
                _bConfigChange = false;
                _onConfigChange();
            }

        }
        public int ParseIpIndex(string ip)
        {
            return _sysConfig.GetIpIndex(ip);
        }
    }

}
