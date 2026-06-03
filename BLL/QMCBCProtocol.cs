using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Hsg.BLL.config;
using Hsg.Common;

namespace Hsg.BLL
{

    /// <summary>
    /// 乾明通讯板的IO控制协议
    /// </summary>
    class QMCBCProtocol : CBCProtocol
    {
        // register addr

        private const ushort REG_ADDR_POWER_SET = 0xA2; // 电源控制
        private const ushort REG_ADDR_EX_PWR_IO_SET = 0xA4; // 测试板PWR脚控制
        private const ushort REG_ADDR_EX_DL_IO_SET = 0xA6; // 测试板DOWNLOAD脚控制

        private const ushort REG_ADDR_DATETIME_SET = 0x78;// 同步时间
        private const ushort REG_ADDR_LOG_ALL_SET = 0x012f;// LOG开关设置 

        private AutoResetEvent _semEvent;
        private bool _haveTask;
        private IoGroupControl _groupTask;// 控制一组的IO任务
        private List<IoControl> _ioControlTasks;// 控制单个IO的任务

        private const ushort INVALID_TIMER = 0xFFFF;
        private Object _taskLock;
        private Stopwatch _stopwatch;
        private double _lastTimeSecond;
        private const string MOD_ID = "QMCBCP";
        private Thread _thread;

        private UInt16 _pwrFlag;
        private UInt16 _pwrFlagTmp;
        private Object _stateLock;
        public QMCBCProtocol()
        {

            _pwrFlag = 0;
            _pwrFlagTmp = 0;
            _stateLock = new object();

            _semEvent = new AutoResetEvent(false);
            _haveTask = false;
            _groupTask = new IoGroupControl();
            _ioControlTasks = new List<IoControl>();
            _taskLock = new object();
            _groupTask.startSec = INVALID_TIMER;
            _stopwatch = new Stopwatch();
            _lastTimeSecond = 0;
            _thread = new Thread(IOControlThreadMain);
            _thread.Start();
            //if (ThreadPool.QueueUserWorkItem(new WaitCallback(IOControlThreadMain),null) == false)
            //{
            //    Hlog.E(MOD_ID, "QMCBCProtocol create thread pool failed.");
            //}
           // await Task.Delay(1000);
        }
        private bool SendComandIOSet(ushort reg, short index, bool enable)
        {
            ushort[] data = new ushort[1];
            if (enable)
            {
                data[0] |= 0x1100;
            }
            data[0] |= (ushort)(1 << index);
            if (_mbMaster == null)
            {
                return false;
            }
            return _mbMaster.WriteMultipleReg(reg, data);
        }

        private bool SendComandIOSet(EIOGroup groupId, short index, bool enable)
        {
            Hlog.I(MOD_ID, "io set:" + groupId + "-" + index + " " + "enable:" + enable);
            switch (groupId)
            {
                case EIOGroup.SWITCH_GROUP_MCU_PWR:
                    return SendComandIOSet(REG_ADDR_EX_PWR_IO_SET, index, enable);
                default:
                    return true;
            }
        }

        private bool SendComandIOGroupSet(ushort reg, UInt16 flag)
        {
            ushort[] data = new UInt16[1] { flag };
            if (_mbMaster == null)
            {
                return false;
            }
            Hlog.I(MOD_ID, "group set:" + reg + " flag:" + flag);
            return _mbMaster.WriteMultipleReg(reg, data);
        }

        private bool SendComandPowerSet(UInt16 pwrFlag)
        {
            return SendComandIOGroupSet(REG_ADDR_POWER_SET, pwrFlag);
        }

        private bool SendCommandGroupSet(EIOGroup groupId, UInt16 flag)
        {
            Hlog.I(MOD_ID, "CommandGroupSet:" + groupId + " flag:" + flag);
            switch (groupId)
            {
                case EIOGroup.SWITCH_GROUP_MCU_PWR:
                    return SendComandIOGroupSet(REG_ADDR_EX_PWR_IO_SET, flag);
                case EIOGroup.SWITCH_GROUP_MCU_KPCOL:
                    return SendComandIOGroupSet(REG_ADDR_EX_DL_IO_SET, flag);
                default:
                    return false;
            }
        }

        private bool SendCommandPowerOffAll()
        {
            if (_mbMaster == null)
            {
                return false;
            }
            return SendComandPowerSet(0x00);
        }

        private bool DateTimeSync()
        {
            ushort[] dateTime = new ushort[6];
            dateTime[0] = (ushort)DateTime.Now.Hour;
            dateTime[1] = (ushort)DateTime.Now.Minute;
            dateTime[2] = (ushort)DateTime.Now.Second;
            dateTime[3] = (ushort)DateTime.Now.Day;
            dateTime[4] = (ushort)DateTime.Now.Month;
            dateTime[5] = (ushort)DateTime.Now.Year;
            if (_mbMaster == null)
            {
                return false;
            }
            return _mbMaster.WriteMultipleReg(REG_ADDR_DATETIME_SET, dateTime);
        }

        //private  bool SendControlComand(UInt16 cmdId, UInt16[] param)
        //{
        //    int paramLen = (param != null ? param.Length : 0);
        //    ushort[] data = new UInt16[paramLen + 1];
        //    data[0] = cmdId;
        //    if (_mbMaster == null)
        //    {
        //        return false;
        //    }
        //    for (int i = 0; i < paramLen; i++)
        //    {
        //        data[i + 1] = param[i];
        //    }
        //    return _mbMaster.WriteMultipleReg(REG_ADDR_CONTROL_CMD, data);
        //}
        private bool SendComandResetTest()
        {
            //TimeSpan span = DateTime.Now.ToUniversalTime() - new DateTime(1970, 1, 1, 0, 0, 0);
            //UInt32 timestamp = (UInt32)span.TotalSeconds;
            //ushort[] timeParam = new ushort[2];
            //timeParam[0] = (ushort)(timestamp & 0xFFFF);
            //timeParam[1] = (ushort)((timestamp >> 16) & 0xFFFF);
            //return SendControlComand(MB_CMD_TEST_RESET, timeParam);
            Hlog.I(MOD_ID, "SendComandResetTest.");
            if (SendCommandGroupSet(EIOGroup.SWITCH_GROUP_MCU_PWR, 0xff) == false)
            {
                Hlog.E(MOD_ID, "request reset mcu pwr faile.");
            }
            if(SendCommandGroupSet(EIOGroup.SWITCH_GROUP_MCU_KPCOL, 0xff) == false)
            {
                Hlog.E(MOD_ID,"request reset mcu kpcol faile.");
            }
            lock(_taskLock)
            {
                _groupTask.startSec = INVALID_TIMER;
                _groupTask.durationSec = INVALID_TIMER;
                _ioControlTasks.Clear();
            }
            return true;
        }

        private bool DoMultiIoCheck(ref UInt16 counterSec)
        {
            UInt16 lastTime = INVALID_TIMER;
            lock (_taskLock)
            {
                if (_groupTask.startSec != INVALID_TIMER) // 还没开始
                {
                    if (_groupTask.startSec < counterSec)
                    {
                        _groupTask.startSec = 0;
                    }
                    else
                    {
                        _groupTask.startSec -= counterSec;
                    }
                    if (_groupTask.startSec == 0) // 时间到，开始执行
                    {
                        if (_groupTask.groupId < (ushort)EIOGroup.SWITCH_GROUP_NUM)
                        {
                            SendCommandGroupSet((EIOGroup)(_groupTask.groupId + EIOGroup.SWITCH_GROUP_START), _groupTask.startStatus);
                        }
                        _groupTask.startSec = INVALID_TIMER;
                        lastTime = _groupTask.durationSec;
                    }
                    else
                    {
                        lastTime = _groupTask.startSec;
                    }

                }
                else if (_groupTask.durationSec != INVALID_TIMER)
                {
                    if (_groupTask.durationSec < counterSec)
                    {
                        _groupTask.durationSec = 0;
                    }
                    else
                    {
                        _groupTask.durationSec -= counterSec;
                    }
                    if (_groupTask.durationSec == 0) // 时间到，开始执行
                    {
                        if (_groupTask.groupId < (ushort)EIOGroup.SWITCH_GROUP_NUM)
                        {
                            SendCommandGroupSet((EIOGroup)(_groupTask.groupId + EIOGroup.SWITCH_GROUP_START), _groupTask.endStatus);
                        }
                        _groupTask.durationSec = INVALID_TIMER;
                    }
                    else
                    {
                        lastTime = _groupTask.durationSec;
                    }
                }

                if (lastTime != INVALID_TIMER)
                {
                    counterSec = lastTime;
                    Hlog.E(MOD_ID, "DoMultiIoCheck:"+ counterSec);
                    return true;
                }
            }

            return false;
        }
        private bool DoIoControlCheck(ref UInt16 counterSec)
        {
            UInt16 nextInterval = INVALID_TIMER;
            lock (_taskLock)
            {
                if (_ioControlTasks.Count > 0)
                {
                    for (int i = _ioControlTasks.Count - 1; i >= 0; i--)
                    {
                        if (_ioControlTasks[i].durationMsec != 0) // 表示有效
                        {
                            if (_ioControlTasks[i].startSec != INVALID_TIMER)// 表示还没开始
                            {
                                if (_ioControlTasks[i].startSec <= counterSec)
                                {
                                    // vSwitchSetGpioStatus(sIOCtrQueue[i].group, sIOCtrQueue[i].line, sIOCtrQueue[i].startStatus);
                                    SendComandIOSet((EIOGroup)_ioControlTasks[i].groupId, _ioControlTasks[i].line, _ioControlTasks[i].startStatus == 0 ? false : true);
                                    _ioControlTasks[i].startSec = INVALID_TIMER;
                                    if (_ioControlTasks[i].durationMsec / 1000 < nextInterval && nextInterval != 1)
                                    {
                                        nextInterval = (ushort)(_ioControlTasks[i].durationMsec / 1000);
                                        if (nextInterval < 1)
                                        {
                                            nextInterval = 1;
                                        }
                                    }
                                }
                                else
                                {
                                    _ioControlTasks[i].startSec -= counterSec;
                                    if (_ioControlTasks[i].startSec < nextInterval)
                                    {
                                        nextInterval = _ioControlTasks[i].startSec;
                                    }
                                }
                            }
                            else
                            {
                                if (_ioControlTasks[i].durationMsec <= counterSec * 1000)
                                {
                                    // vSwitchSetGpioStatus(sIOCtrQueue[i].group, sIOCtrQueue[i].line, sIOCtrQueue[i].startStatus ? RESET : SET);
                                    SendComandIOSet((EIOGroup)_ioControlTasks[i].groupId, _ioControlTasks[i].line, _ioControlTasks[i].startStatus == 0 ? true : false);
                                    _ioControlTasks[i].durationMsec = 0;
                                    _ioControlTasks.RemoveAt(i);
                                }
                                else
                                {
                                    _ioControlTasks[i].durationMsec -= (ushort)(counterSec * 1000);
                                    if (_ioControlTasks[i].durationMsec / 1000 < nextInterval && nextInterval != 1)
                                    {
                                        nextInterval = (ushort)(_ioControlTasks[i].durationMsec / 1000);
                                        if (nextInterval < 1)
                                        {
                                            nextInterval = 1;
                                        }
                                    }
                                }
                            }
                        }
                    }
                    counterSec = nextInterval;
                    return true;
                }
            }
            counterSec = nextInterval;
            return false;
        }
        private void IOControlThreadMain()
        {
            Hlog.I(MOD_ID, "IOControlThreadMain.");
            while (true)
            {
                UInt16 interval = 1;
                if (_haveTask)
                {
                    bool taskCheck = false;
                    UInt16 multiInterval = 0;
                    UInt16 singleInterval = 0;
                    if (!_stopwatch.IsRunning)
                    {
                        interval = 0;
                    }
                    else
                    {
                        // 由于使用秒单位，ushort ，所以误差在1S以内
                        interval = (ushort)(_stopwatch.Elapsed.TotalSeconds - _lastTimeSecond);
                        _lastTimeSecond += interval;
                        Hlog.I(MOD_ID, "lasttime:" + _lastTimeSecond);
                    }

                    singleInterval = interval;
                    multiInterval = interval;
                    Hlog.I(MOD_ID, "interval:" + interval);
                    if (DoMultiIoCheck(ref multiInterval))
                    {
                        taskCheck = true;
                        interval = multiInterval;
                        Hlog.I(MOD_ID, "multiocheck exist:" + interval);
                    }

                    if (DoIoControlCheck(ref singleInterval))
                    {
                        //有更近的需要执行的任务 ||没有设置过interval

                        if (singleInterval < interval 
                            ||!taskCheck)
                          
                        {
                            interval = singleInterval;
                        }
                        taskCheck = true;
                        Hlog.I(MOD_ID, "iocheck exist:" + interval);
                    }
                    if (taskCheck)
                    {
                        if (!_stopwatch.IsRunning)
                        {
                            Hlog.I(MOD_ID, "start stopwatch");
                            _lastTimeSecond = 0;
                            _stopwatch.Start();
                        }
                        _haveTask = true;
                        _semEvent.WaitOne(interval * 1000, true);

                    } else
                    {
                        _haveTask = false;
                        if (_stopwatch.IsRunning)
                        {
                            Hlog.I(MOD_ID, "reset stopwatch");
                            _lastTimeSecond = 0;
                            _stopwatch.Reset();
                        }
                    }
                    // do task.
                }
                else
                {
                    Hlog.I(MOD_ID, "qmcbc WaitOne");
                    _semEvent.WaitOne();
                    _haveTask = true;
                }

            }

        }
        // override function.
        #region override functions
        public override bool StartConnect(MBConfig config)
        {
            return _mbMaster.StartConnect(config);
        }
        public override bool Disconnect()
        {
            _mbMaster.DoDisconnect();
            return true;
        }
        public override bool InitAllGpio()
        {
            Hlog.I(MOD_ID, "InitAllGpio");
            if (DateTimeSync())
            {
                return true;
            }
            return false;
        }
        public override bool ResetAllGpio()
        {
            Hlog.I(MOD_ID, "ResetAllGpio");
            return SendComandResetTest();
        }
        public override bool PowerSet(ushort flag)
        {
            lock (_stateLock)
            {
                _pwrFlag = flag;
                _pwrFlagTmp = flag;
            }
            return SendComandPowerSet(flag);
        }
        public override bool PowerOffAll()
        {
            lock (_stateLock)
            {
                _pwrFlag = 0;
                _pwrFlagTmp = 0;
            }
            return SendCommandPowerOffAll();
        }
        public override bool SetIOControl(ushort[] param)
        {
            IoControl ioControl = new IoControl();
            ioControl.LoadFromData(param);
            Hlog.I(MOD_ID, "SetIOControl:" + ioControl.groupId +" line:" + ioControl.line + " start:" + ioControl.startSec);
            lock (_taskLock)
            {
                if (_stopwatch.IsRunning)
                {
                    ushort interval = (ushort)(_stopwatch.Elapsed.TotalSeconds - _lastTimeSecond);
                    ioControl.startSec += interval;
                }

                _ioControlTasks.Add(ioControl);
                _semEvent.Set();
            }
            return true;
        }
        public override bool SetIOGroup(ushort[] param)
        {
            //return SendControlComand(MB_CMD_MULT_IO_SET, param);
            IoGroupControl ioGroup = new IoGroupControl();
            ioGroup.LoadFromData(param);
            lock (_taskLock)
            {
                if (_stopwatch.IsRunning)
                {
                    ushort interval = (ushort)(_stopwatch.Elapsed.TotalSeconds - _lastTimeSecond);
                    ioGroup.startSec += interval;
                    
                }
                //else
                //{
                //        _lastTimeSecond = 0;
                //        _stopwatch.Start();
                //}
                _groupTask = ioGroup;
                _semEvent.Set();
                Hlog.I(MOD_ID, "SetIOGroup：" + ioGroup.groupId + "-" + ioGroup.startStatus);
            }
            
            return true;
        }

        public override bool RebootAll()
        {
            return true;
        }
        // 只修改状态不发送指令
        public override bool PowerChange(bool enable, uint index)
        {
            if (index >= 0 && index < 8)
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
                }
               // return SendComandPowerSet(_pwrFlag);
            }

            return true;
        }

        public override bool SyncPowerStatus()
        {
            lock (_stateLock)
            {
                if (_pwrFlagTmp == _pwrFlag)
                {
                    return true;
                }
                _pwrFlag = _pwrFlagTmp;
            }
            SendComandPowerSet(_pwrFlag);
            return true;
        }


        public override bool CheckIpIsReady(string IpAddr)
        {
            return Tools.PingIp(IpAddr, 50);
        }

        public override bool SetIOGroup(int ioId, ushort flag)
        {
            throw new NotImplementedException();
        }

        public override void BindOnlineStateChange(Action<bool> OnStateChange, int ipIndex)
        {
            
        }
        #endregion
    }
}
