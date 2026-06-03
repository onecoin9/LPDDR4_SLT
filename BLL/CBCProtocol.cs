using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Hsg.BLL.config;
/// <summary>
/// Communicate Board Control Protocol 
/// </summary>
namespace Hsg.BLL
{
    struct IoGroupControl
    {
        public UInt16 groupId;
        public Byte startStatus; // 0 or 1
        public Byte endStatus;
        public UInt16 startSec;
        public UInt16 durationSec;
        public UInt16[] GenerateShortPackage()
        {
            UInt16[] outPackage = new UInt16[4];
            outPackage[0] = groupId;
            outPackage[1] = (UInt16)(startStatus | (endStatus << 8));
            outPackage[2] = startSec;
            outPackage[3] = durationSec;
            return outPackage;
        }
        public bool LoadFromData(UInt16[] data)
        {
            if (data.Length != 4)
            {
                return false;
            }
            groupId = data[0];
            startStatus = (byte)(data[1] & 0xff);
            endStatus = (byte)((data[1] >> 8) & 0xff);
            startSec = data[2];
            durationSec = data[3];
            return true;
        }
    };
    class IoControl
    {
        public UInt16 groupId;
        public Byte line;//
        public Byte startStatus;// 0,1
        public UInt16 startSec;
        public UInt16 durationMsec;
        public UInt16[] GenerateShortPackage()
        {
            UInt16[] outPackage = new UInt16[4];
            outPackage[0] = groupId;
            outPackage[1] = (UInt16)(line | (startStatus << 8));
            outPackage[2] = startSec;
            outPackage[3] = durationMsec;
            return outPackage;
        }
        public bool LoadFromData(UInt16[] data)
        {
            if (data.Length != 4)
            {
                return false;
            }
            groupId = data[0];
            line = (byte)(data[1] & 0xff);
            startStatus = (byte)((data[1] >> 8) & 0xff);
            startSec = data[2];
            durationMsec = data[3];
            return true;
        }
        public IoControl()
        { }
    };

    public enum EIOGroup
    {
        SWITCH_GROUP_START,
        SWITCH_GROUP_PWR_EN = SWITCH_GROUP_START,
        // SWITCH_GROUP_MCU_RST,
        //  SWITCH_GROUP_MCU_EINT,
        SWITCH_GROUP_MCU_PWR,
        SWITCH_GROUP_MCU_KPCOL,
        SWITCH_GROUP_NUM,
        SWITCH_GROUP_INVALID = 0xFF,
    };

    public abstract class CBCProtocol
    {
        protected MBMaster _mbMaster;
        public const UInt32 TOTAL_GPIO_LINE = 12;
        /// <summary>
        /// 用于精准控制IO高低过程的请求序号 >=1
        /// </summary>
        private UInt16 _IOCtrSerial;
        /// <summary>
        /// 
        /// </summary>
        /// <param name="ioId">EIOGroup</param>
        /// <param name="statTime"></param>
        /// <param name="spanTime"></param>
        /// <param name="package"></param>
        /// <returns></returns>
        static public bool GenerateGroupSetPackage(int ioId, ushort statTime, ushort spanTime, out UInt16[] package)
        {
            package = null;
            IoGroupControl control = new IoGroupControl(); ;
            if (ioId >= (int)EIOGroup.SWITCH_GROUP_START && ioId < (int)EIOGroup.SWITCH_GROUP_NUM) //
            {
                switch ((EIOGroup)ioId)
                {
                    case EIOGroup.SWITCH_GROUP_PWR_EN:

                        control.groupId = (ushort)ioId;
                        control.startSec = statTime;
                        control.durationSec = spanTime;
                        control.startStatus = 0xff;
                        control.endStatus = 0x00;
                        break;
                    //case EIOGroup.SWITCH_GROUP_MCU_RST:
                    case EIOGroup.SWITCH_GROUP_MCU_PWR:
                        //case EIOGroup.SWITCH_GROUP_MCU_EINT:
                        control.groupId = (ushort)ioId;
                        control.startSec = statTime;
                        control.durationSec = spanTime;
                        control.startStatus = 0x00;
                        control.endStatus = 0xff;
                        break;
                    case EIOGroup.SWITCH_GROUP_MCU_KPCOL:
                        control.groupId = (ushort)ioId;
                        control.startSec = statTime;
                        control.durationSec = spanTime;
                        control.startStatus = 0x00;
                        control.endStatus = 0x00;
                        break;
                }
                package = control.GenerateShortPackage();
                return true;
            }
            return false;
        }

        static public bool GroupIoCtrGetFlag(int ioId, bool isStart, out UInt16 flag, UInt16 lineCount = 16)
        {
            flag = 0;
            UInt16 targetFlag = 0;
            if (ioId >= (int)EIOGroup.SWITCH_GROUP_START && ioId < (int)EIOGroup.SWITCH_GROUP_NUM && lineCount <= 16) //
            {
                switch ((EIOGroup)ioId)
                {
                    case EIOGroup.SWITCH_GROUP_PWR_EN:
                        if (isStart)
                        {
                            targetFlag = 0xffff;
                        }
                        else
                        {
                            targetFlag = 0x0000;
                        }
                        break;
                    //case EIOGroup.SWITCH_GROUP_MCU_RST:
                    case EIOGroup.SWITCH_GROUP_MCU_PWR:
                        if (isStart)
                        {
                            targetFlag = 0x00;
                        }
                        else
                        {
                            targetFlag = 0xffff;
                        }
                        break;
                    case EIOGroup.SWITCH_GROUP_MCU_KPCOL:
                        targetFlag = 0x00;
                        break;
                }
                flag = (UInt16)(targetFlag ^ (0xFFFF << lineCount));
                return true;
            }
            return false;
        }

        static public bool GenerateIOSetPackage(int ioId, byte line, ushort statSec, ushort spanMsec, out UInt16[] package)
        {
            package = null;
            IoControl control = new IoControl();
            if (ioId >= (int)EIOGroup.SWITCH_GROUP_START && ioId < (int)EIOGroup.SWITCH_GROUP_NUM) //
            {
                switch ((EIOGroup)ioId)
                {
                    case EIOGroup.SWITCH_GROUP_PWR_EN:
                        control.groupId = (ushort)ioId;
                        control.startSec = statSec;
                        control.durationMsec = spanMsec;
                        control.startStatus = 1;
                        control.line = line;
                        break;
                    //case EIOGroup.SWITCH_GROUP_MCU_RST:
                    //case EIOGroup.SWITCH_GROUP_MCU_EINT:
                    case EIOGroup.SWITCH_GROUP_MCU_PWR:
                    case EIOGroup.SWITCH_GROUP_MCU_KPCOL:
                        control.groupId = (ushort)ioId;
                        control.startSec = statSec;
                        control.durationMsec = spanMsec;
                        control.startStatus = 0;
                        control.line = line;
                        break;
                }
                package = control.GenerateShortPackage();
                return true;
            }
            return false;
        }
        private static void GetoutGroupData(uint totalTime, uint getTime, out uint[] groupdata)
        {
            if (getTime < 1 || getTime > totalTime)
            {
                groupdata = null;
                return;
            }

            const uint totalNumbers = TOTAL_GPIO_LINE;
            uint numbersPerBatch = totalNumbers / totalTime;
            uint extraNumbers = totalNumbers % totalTime;

            uint startIndex, endIndex;

            if (getTime <= extraNumbers)
            {
                startIndex = (getTime - 1) * (numbersPerBatch + 1);
                endIndex = startIndex + (numbersPerBatch + 1);
            }
            else
            {
                startIndex = extraNumbers * (numbersPerBatch + 1) + (getTime - extraNumbers - 1) * numbersPerBatch;
                endIndex = startIndex + numbersPerBatch;
            }

            // 确保最后一个批次包含剩余数字
            if (getTime == totalTime)
                endIndex = totalNumbers;

            List<uint> batch = new List<uint>();

            for (uint i = startIndex; i < endIndex; i++)
            {
                uint group = i % 3;
                uint numInGroup = i / 3;
                uint value = group * 4 + numInGroup + 1;
                batch.Add(value);
            }

            groupdata = batch.ToArray();
        }
        /// <summary>
        /// 
        /// </summary>
        /// <param name="ioId"></param>
        /// <param name="batch">分几个批次</param>
        /// <param name="statSec">最初启动时间</param>
        /// <param name="intervalSec">启动间隔</param>
        /// <param name="spanMsec">持续时间</param>
        /// <param name="package"></param>
        static public void GenerateIoSecuritySetPackage(UInt16 ioCtrSerial,int ioId, UInt32 batch, ushort statSec, ushort intervalSec, ushort spanMsec, out UInt16[] package)
        {
            ushort setStartSec = statSec;
            package = null;
            List<ushort> dataList = new List<ushort>();
            dataList.Add(ioCtrSerial);
            for (uint i = 1; i <= batch; i++)
            {
                uint[] lineIds = Array.Empty<uint>();
                GetoutGroupData(batch, i, out lineIds);
                foreach (var v in lineIds)
                {
                    ushort[] outData = Array.Empty<ushort>();
                    GenerateIOSetPackage(ioId, (byte)(v-1), setStartSec, spanMsec, out outData);
                    foreach(var vd in outData)
                    {
                        dataList.Add(vd);
                    }
                }
                setStartSec += intervalSec;
            }
            package = dataList.ToArray();
        }
        public CBCProtocol()
        {
            _IOCtrSerial = 1;
            _mbMaster = new MBMaster();
        }
        public void StartNewIOControl()
        {
            _IOCtrSerial++;
            if (_IOCtrSerial == 0)
            {
                _IOCtrSerial = 1;
            }
        }
        public UInt16 GetIOControlSerial()
        {
            return _IOCtrSerial;
        }
        public abstract bool StartConnect(MBConfig config);
        public abstract bool Destory();
        public abstract bool InitAllGpio();
        public abstract bool ResetAllGpio();
        public abstract bool PowerSet(ushort flag);
        public abstract bool PowerOffAll();
        public abstract bool RebootAll();
        public abstract bool SetIOControl(ushort[] param);
        public abstract bool SetIOSecurityControl(ushort[] param);
        public abstract bool SetIOGroup(ushort[] param);
        public abstract bool SetIOGroup(int ioId, ushort flag);
        // 修改duts 状态 不发送指令配合 syncPowerStatus 使用
        public abstract bool PowerChange(bool enable, uint index);
        //同步duts 结果
        public abstract bool SyncPowerStatus();
        /// <summary>
        /// 判断对应地址是否就绪
        /// </summary>
        /// <param name="IpAddr"></param>
        /// <returns></returns>
        public abstract bool ClearReadyState(string IpAddr);
        /// <summary>
        /// 判断对应地址是否就绪
        /// </summary>
        /// <param name="IpAddr"></param>
        /// <returns></returns>
        public abstract bool CheckIpIsReady(string IpAddr);
        /// <summary>
        /// 用来绑定检测板卡是否在线，暂时只有上线消息，没有下线。
        /// </summary>
        /// <param name="OnStateChange"></param>
        /// <param name="ipIndex"></param>
        public abstract void BindOnlineStateChange(Action<bool> OnStateChange, int ipIndex);
        ///// <summary>
        ///// 是否就绪
        ///// </summary>
        //public bool IsReady;
        ///// <summary>
        ///// 获取初始化后的错误信息
        ///// </summary>
        ///// <returns></returns>
        //public abstract string GetStateError();
    }
}
