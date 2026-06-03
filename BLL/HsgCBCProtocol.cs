using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Hsg.BLL.config;
using Hsg.Common;
using System.Net;
using Hsg.BLL.Net;
using System.Runtime.InteropServices;
using System.Threading;

namespace Hsg.BLL
{
    // demo data AF 00 00 00 00 00 00 00 E3 D6 A1 66 00 00 00 00 E3 D6 A1 66 FE 00 00 00
    internal struct BroadcastPackage
    {
        public UInt32 head;// 0xAF
        public UInt32 targetId; // 目标ID
        public UInt32 serial;// 授权序号。不同的序号代表新的开始
        public UInt32 ipAddr;//
        public UInt32 checkSum;
        public UInt32 tail;// 0xFE
    };

    internal struct BroadcastAck
    {
        public UInt32 head;// 0xAF
        public UInt32 deviceId; // 设备ID 广播查询所有的时候（未指定ID）会收到ID，其他时候（指定ID）为0,可以用来识别是广播的回复还是普通通讯回复
        public UInt32 serial;// 授权序号。
        public UInt32 checkSum;
        public UInt32 tail;// 0xFE
    };

    internal class HsgBroadcast
    {
        // broadcast package. 
        private const UInt32 HEAD_BYTES = 0xAF;
        private const UInt32 TAIL_BYTES = 0xFE;

        private SysConfig _config;
        private UdpServer _udpServer;
        private Timer _broadcastTimer;
        private UInt32 _startTimestamp;
        private static readonly Object _classLock = new object();
        private static HsgBroadcast _instance;
        private bool _closed = false;
        public static HsgBroadcast Instance
        {
            get
            {
                if (_instance == null)
                {
                    lock (_classLock)
                    {
                        if (_instance == null)
                        {
                            _instance = new HsgBroadcast();
                        }
                    }
                }
                return _instance;
            }
        }
        private int _sendPort = 10000;
        //private int _recvPort = 10001;
        private HashSet<string> _detectedAddrList;
        private SortedList<int, Action<bool>> _stateChangeNotifyList = new SortedList<int, Action<bool>>();
        private HsgBroadcast()
        {
            _config = SysConfig.GetInstance();
            _udpServer = new UdpServer(UdpRecvDataHandle);
            _detectedAddrList = new HashSet<string>();
            _sendPort = SysConfig.BroadcastPortForBoard;
            _udpServer.Start();
            TimeSpan span = DateTime.Now.ToUniversalTime() - new DateTime(1970, 1, 1, 0, 0, 0);
            _startTimestamp = (uint)span.TotalSeconds;
            _broadcastTimer = new Timer(StartStatusDetect, null, 3000, 5000);
        }
        public void StartStatusDetect(object state)
        {
            Task.Run(() => ServerBroadCastForBoard());
        }
        private static UInt32 ConventIpBitOrder(UInt32 ipAddr)
        {
            UInt32 outIp = ((ipAddr & 0x000000FF) << 24);
            outIp |= ((ipAddr & 0x0000FF00) << 8);
            outIp |= ((ipAddr & 0x00FF0000) >> 8);
            outIp |= ((ipAddr & 0xFF000000) >> 24);
            return outIp;
        }
        public void AddStateChangeNotify(int ipIndex, Action<bool> onStateChange)
        {
            lock (_classLock)
            {
                _stateChangeNotifyList.Add(ipIndex, onStateChange);
            }
        }
        private void EncodeAddrPackage(UInt32 ipAddr, UInt32 serial, UInt32 targetId, out byte[] package)
        {
            BroadcastPackage broadcastPackage = new BroadcastPackage();
            int size = Marshal.SizeOf<BroadcastPackage>();
            UInt32 lastIp = ConventIpBitOrder(ipAddr);
            broadcastPackage.head = HEAD_BYTES;
            broadcastPackage.targetId = targetId;
            broadcastPackage.checkSum = targetId;
            broadcastPackage.checkSum += serial;
            broadcastPackage.serial = serial;
            broadcastPackage.ipAddr = lastIp;
            broadcastPackage.checkSum += lastIp;
            broadcastPackage.tail = TAIL_BYTES;
            package = HConvent.StructToBytes<BroadcastPackage>(broadcastPackage);
        }

        public static bool DecodeAckPackage(byte[] package, ref UInt32 deviceId, ref UInt32 serial)
        {
            int size = Marshal.SizeOf<BroadcastAck>();
            if (package.Length == size)
            {
                BroadcastAck ack = HConvent.BytesToStruct<BroadcastAck>(package);
                UInt32 checkSum = ack.deviceId + ack.serial;
                if (checkSum == ack.checkSum)
                {
                    deviceId = ack.deviceId;
                    serial = ack.serial;
                    return true;
                }
            }
            return false;
        }
        private void ServerBroadCastForBoard()
        {
            IPEndPoint point = new IPEndPoint(IPAddress.Parse(SysConfig.BroadcastAddrForBoard), _sendPort);
            byte[] data = null;
            EncodeAddrPackage(0, _startTimestamp, 0, out data);
            _udpServer.SendData(data, point);
        }
        public bool CheckIpIsReady(string ipAddr)
        {
            return _detectedAddrList.Contains(ipAddr);
        }
        public bool ClearReadyIp(string ipAddr)
        {
            if (_detectedAddrList.Contains(ipAddr))
            {
                _detectedAddrList.Remove(ipAddr);
            }
            return true;
        }
        private bool UdpRecvDataHandle(byte[] data, IPEndPoint ipEndPoint)
        {
            uint deviceId = 0;
            uint serial = 0;

            IPEndPoint boardIp = ipEndPoint;
            boardIp.Port = _sendPort;
            byte[] addrBytes = ipEndPoint.Address.GetAddressBytes();
            if (DecodeAckPackage(data, ref deviceId, ref serial))
            {
                if (deviceId != 0 && serial == _startTimestamp)
                {
                    EncodeAddrPackage(0, _startTimestamp, deviceId, out data);
                    _udpServer.SendData(data, boardIp);
                    _detectedAddrList.Add(ipEndPoint.Address.ToString());
                    int ipIndex = _config.GetIpIndex(ipEndPoint.Address.ToString());
                    if (ipIndex >= 0)
                    {
                        Action<bool> notifyAction = null;
                        if (_stateChangeNotifyList.TryGetValue(ipIndex, out notifyAction))
                        {
                            notifyAction.Invoke(true);
                        }
                    }
                }
            }
            return true;
        }
        public void Destory()
        {
            lock (_classLock)
            {
                if (!_closed)
                {
                    _closed = true;
                    _broadcastTimer.Dispose();
                    _udpServer.Stop();
                }
            }

        }
    }
    /// <summary>
    /// 宏芯宇自己通讯板的IO控制协议
    /// </summary>
    public class HsgCBCProtocol : CBCProtocol
    {
        // register addr
        private const ushort REG_ADDR_DEVICE_ID = 0xF8;// 设备信息
        private const ushort REG_ADDR_POWER_SET = 0xA2; // 电源控制
        private const ushort REG_ADDR_MCU_PWR_SET = 0xA4;
        private const ushort REG_ADDR_MCU_KPCOL_SET = 0xA6;

        private const ushort REG_ADDR_CONTROL_CMD = 0xF000; // 用于发送特殊控制指令
        private const ushort REG_ADDR_CONTROL_STATUS = 0xF001;// 读取设备执行状态
        // 特殊控制指令集合
        private const ushort MB_CMD_OTA = 0x01;// 控制升级
        private const ushort MB_CMD_MULT_IO_SET = 0x02;// 控制IO延迟开启
        private const ushort MB_CMD_REBOOT = 0x03;// 重启
        private const ushort MB_CMD_SAVE_CONFIG = 0x04;// 重启
        private const ushort MB_CMD_IO_SET = 0x05;// 控制单个IO延迟set/reset 保持多久
        private const ushort MB_CMD_TEST_RESET = 0x06;// 复位测试 
        private const ushort MB_CMD_IO_SECURITY_SET = 0x07;//设置一组IO 安全方式，避免重复执行


        private UInt16 _pwrFlag;
        private UInt16 _pwrFlagTmp;
        private Object _stateLock;
        private HsgBroadcast _hsgBroadcast;
#if _DEBUG_ON
        private const bool DebugMode = true;//  调试用
#else
        private const bool DebugMode = false;//  调试用
#endif
        public HsgCBCProtocol()
        {
            _pwrFlag = 0;
            _pwrFlagTmp = 0;
            _stateLock = new object();
            _hsgBroadcast = HsgBroadcast.Instance;
        }

        private bool SendComandPowerSet(UInt16 pwrFlag)
        {
            ushort[] data = new UInt16[1] { pwrFlag };
            if (_mbMaster == null)
            {
                return false;
            }
            Hlog.I("SendComandPowerSet:" + pwrFlag.ToString("X2"));
            return _mbMaster.WriteMultipleReg(REG_ADDR_POWER_SET, data);
        }

        private bool SendComandMcuPower(UInt16 pwrFlag)
        {
            ushort[] data = new UInt16[1] { pwrFlag };
            if (_mbMaster == null)
            {
                return false;
            }
            return _mbMaster.WriteMultipleReg(REG_ADDR_MCU_PWR_SET, data);
        }

        private bool SendComandMcuKpCol(UInt16 flag)
        {
            ushort[] data = new UInt16[1] { flag };
            if (_mbMaster == null)
            {
                return false;
            }
            return _mbMaster.WriteMultipleReg(REG_ADDR_MCU_KPCOL_SET, data);
        }

        private bool SendCommandPowerOffAll()
        {
            if (_mbMaster == null)
            {
                return false;
            }
            return SendComandPowerSet(0x00);
        }

        private bool ReadDeviceId(ref ushort[] deviceId)
        {
            if (_mbMaster == null)
            {
                return false;
            }
            return _mbMaster.ReadMultipleReq(REG_ADDR_DEVICE_ID, 2, deviceId);
        }

        private bool SendControlComand(UInt16 cmdId, UInt16[] param)
        {
            int paramLen = (param != null ? param.Length : 0);
            ushort[] data = new UInt16[paramLen + 1];
            data[0] = cmdId;
            if (_mbMaster == null)
            {
                return false;
            }
            for (int i = 0; i < paramLen; i++)
            {
                data[i + 1] = param[i];
            }
            return _mbMaster.WriteMultipleReg(REG_ADDR_CONTROL_CMD, data);
        }
        private bool SendComandResetTest()
        {
            TimeSpan span = DateTime.Now.ToUniversalTime() - new DateTime(1970, 1, 1, 0, 0, 0);
            UInt32 timestamp = (UInt32)span.TotalSeconds;
            ushort[] timeParam = new ushort[2];
            timeParam[0] = (ushort)(timestamp & 0xFFFF);
            timeParam[1] = (ushort)((timestamp >> 16) & 0xFFFF);
            return SendControlComand(MB_CMD_TEST_RESET, timeParam);
        }
        // override function.
        #region override functions
        public override bool StartConnect(MBConfig config)
        {
            return _mbMaster.StartConnect(config);
        }
        public override bool Destory()
        {
            _mbMaster.DoDisconnect();
            _hsgBroadcast.Destory();
            return true;
        }
        public override bool InitAllGpio()
        {
            ushort[] deviceId = new UInt16[2];
            int _deviceId = 0;
#if _DEBUG_ON
            if (DebugMode)
            {
                return true;
            }
#endif
            if (ReadDeviceId(ref deviceId))
            {
                _deviceId = deviceId[0] + (deviceId[1] << 16);
                Hlog.E("read id ok " + _deviceId.ToString());
                return true;
            }
            return false;
        }
        public override bool ResetAllGpio()
        {
#if _DEBUG_ON
            if (DebugMode)
            {
                return true;
            }
#endif
            return SendComandResetTest();
        }
        public override bool PowerSet(ushort flag)
        {
            lock (_stateLock)
            {
                _pwrFlag = flag;
                _pwrFlagTmp = flag;
            }
#if _DEBUG_ON
            if (DebugMode)
            {
                return true;
            }
#endif
            return SendComandPowerSet(flag);
        }
        public override bool PowerOffAll()
        {
            lock (_stateLock)
            {
                _pwrFlag = 0;
                _pwrFlagTmp = 0;
            }
#if _DEBUG_ON
            if (DebugMode)
            {
                return true;
            }
#endif
            return SendCommandPowerOffAll();
        }
        public override bool SetIOControl(ushort[] param)
        {
#if _DEBUG_ON
            if (DebugMode)
            {
                return true;
            }
#endif
            return SendControlComand(MB_CMD_IO_SET, param);
        }

        public override bool SetIOSecurityControl(ushort[] param)
        {
#if _DEBUG_ON
            if (DebugMode)
            {
                return true;
            }
#endif
            return SendControlComand(MB_CMD_IO_SECURITY_SET, param);
        }
        public override bool SetIOGroup(ushort[] param)
        {
#if _DEBUG_ON
            if (DebugMode)
            {
                return true;
            }
#endif
            return SendControlComand(MB_CMD_MULT_IO_SET, param);
        }

        public override bool RebootAll()
        {
#if _DEBUG_ON
            if (DebugMode)
            {
                return true;
            }
#endif
            return SendControlComand(MB_CMD_REBOOT, null);
        }
        // 只修改状态不发送指令
        public override bool PowerChange(bool enable, uint index)
        {
            if (index >= 0 && index < 12)
            {
                lock (_stateLock)
                {
                    if (enable)
                    {
                        _pwrFlagTmp |= (ushort)(1 << (int)index);
                    }
                    else
                    {
                        _pwrFlagTmp &= (ushort)~(1 << (int)index);
                    }
                    Hlog.D("PowerChange:" + _pwrFlagTmp.ToString("X2"));
                }
                // return SendComandPowerSet(_pwrFlag);
            }

            return true;
        }

        public override bool SyncPowerStatus()
        {
            lock (_stateLock)
            {
                Hlog.D("SyncPowerStatus:" + _pwrFlagTmp.ToString("X2"));
                if (_pwrFlagTmp == _pwrFlag)
                {
                    return true;
                }
                _pwrFlag = _pwrFlagTmp;
            }
#if _DEBUG_ON
            if (DebugMode)
            {
                return true;
            }
#endif
            SendComandPowerSet(_pwrFlag);
            return true;
        }




        public override bool CheckIpIsReady(string IpAddr)
        {
#if _DEBUG_ON
            if (DebugMode)
            {
                return true;
            }
#endif
            return _hsgBroadcast.CheckIpIsReady(IpAddr);
        }

        public override bool SetIOGroup(int ioId, ushort flag)
        {
#if _DEBUG_ON
            if (DebugMode)
            {
                return true;
            }
#endif
            switch ((EIOGroup)ioId)
            {
                case EIOGroup.SWITCH_GROUP_PWR_EN:
                    return SendComandPowerSet(flag);
                //case EIOGroup.SWITCH_GROUP_MCU_RST:
                case EIOGroup.SWITCH_GROUP_MCU_PWR:
                    return SendComandMcuPower(flag);
                case EIOGroup.SWITCH_GROUP_MCU_KPCOL:
                    return SendComandMcuKpCol(flag);
            }
            return false;
        }

        public override void BindOnlineStateChange(Action<bool> OnStateChange, int ipIndex)
        {
            _hsgBroadcast.AddStateChangeNotify(ipIndex, OnStateChange);
        }

        public override bool ClearReadyState(string IpAddr)
        {
            return _hsgBroadcast.ClearReadyIp(IpAddr);
        }
        #endregion


    }
}
