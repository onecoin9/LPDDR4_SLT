using System;
using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Text;
using System.Threading.Tasks;
using Hsg.BLL;
using Hsg.BLL.Net;
using Hsg.Common;

namespace Hsg.BLL
{
    public struct PowerSet
    {
        public UInt16 startSec;
        public UInt16 spanMsec;
    }
    /// <summary>
    /// 负责UDP的通讯执行单个测试逻辑
    /// </summary>
    public partial class DutMaster
    {
        //private const string MOD_ID = "DUT";
        private ushort _statusCode = StateCode.SCODE_INVALID;// 测试反馈的状态码
        public PowerSet powerSet;
        public int _instanceId;
        public int _groupId;
        private UInt32 _recordInstance = CSVRecord.INVALID_INSTANCE_ID;// csv record instance id
        public string _testInfor;// 测试反馈的附带信息（容量，die,rank等）
        private int _dutRecordLastId; // dut Record cmd instance id
        private UInt32 _teamStartTimestamp;// 开始的时间戳（秒），同一组里的dut 相同
        private CSVRecord _testInfoCSV;
        private string _testBoardSW;//测试板的版本信息
        private UInt16 _lastCmd;// udp 接收的最后命令ID
        private bool _teampCtrMainBoardError;// 是否所有温控失联
        private string _stageInfo;// 测试的附加信息
        private string _repeatInfo;// 测试的附加信息
        private string _taskSerialNo;// 测试任务关联ID
       // private bool _debug_flag = true;
		private TestBoardConfig _testBoardCfg;
        public override void Run()
        {
            StartSync(DutStatus.ST_READY);
        }

        private void OnPostEventAsyncToTeam(DutEvent_E evt, int instanceId)
        {
            if (_onDutPostEventAsync != null)
            {
                _onDutPostEventAsync(evt, instanceId);
            }
        }
        public bool RecvDataHandle(byte[] data)
        {
            Hlog.I(Mod, "recv data len:" + data.Length);
            if (CurState >= DutStatus.ST_WAIT_BEGING && CurState < DutStatus.ST_TEST_END)
            {
                byte cmdId;
                byte[] decodeData = new byte[1];
                short dataLen = 0;
                IPEndPoint ipEndPiont = new IPEndPoint(IPAddress.Parse(_senderConfig.IP), Int32.Parse(_senderConfig.TxPort));
                DutProtocol.ErrorCode error = DutProtocol.DecodeCmdPackage(data, out cmdId, ref decodeData, out dataLen);
                if (error == DutProtocol.ErrorCode.ER_OK)
                {
                    byte[] ack = DutProtocol.GenerateAckPackage(cmdId, 0);
                    Hlog.I(Mod, "recv cmdId:" + cmdId);
                    if (cmdId == DutProtocol.SLAVE_CMD_READY)
                    {
                        if (_lastCmd != cmdId)
                        {
                            String ver = "";
                            if (DutProtocol.ParseStartReady(decodeData, decodeData.Length, ref ver))
                            {
                                _testBoardSW = ver;
                                PostEventAsync(DutEvent_I.EVT_SLAVE_READY);
                                _lastCmd = cmdId;
                            }
                            _dutSender.SendData(ack, ipEndPiont);
                        }
                        else
                        {
                            _dutSender.SendData(ack, ipEndPiont);
                        }
                        //AppendLogToUi("-->设备准备就绪", LOG_TYPE.INFO);
                    }
                    else if (cmdId == DutProtocol.SLAVE_CMD_TEST_INFO)
                    {
                        Hlog.D(Mod, "recv SLAVE_CMD_TEST_INFO");
                        if (_lastCmd != cmdId)
                        {
                            // if(_debug_flag)
                            //{
                            //    _debug_flag = false;
                            //    byte[] testData = new byte[] { 0, 0, 1, 1 };
                            //    _dutSender.SendData(testData, ipEndPiont);
                            //    Hlog.D(Mod, "send debug data");
                            //}
                            if (DutProtocol.ParseTestInfor(decodeData, decodeData.Length, ref _testInfor))
                            {
                                _dutSender.SendData(ack, ipEndPiont);
                                PostEventAsync(DutEvent_I.EVT_SLAVE_TEST_INFO);
                                //AppendLogToUi("-->读取到存储信息:" + _testInfor, LOG_TYPE.INFO);
                                _lastCmd = cmdId;
                               // _debug_flag = true;
                            }
                            PostEventAsync(DutEvent_I.EVT_SLAVE_EXEC_CMD, cmdId);
                        }
                        else
                        {
                            _dutSender.SendData(ack, ipEndPiont);
                        }
                    }
                    else if (cmdId == DutProtocol.SLAVE_CMD_AGING_TIME)
                    {
                        if(_lastCmd != cmdId)
                        {
                            _lastCmd = cmdId;
                            PostEventAsync(DutEvent_I.EVT_SLAVE_EXEC_CMD, cmdId);
                            ack = DutProtocol.GenerateAginTimeAckPackage(_testBoardCfg.AginTime);
                            _dutSender.SendData(ack, ipEndPiont);
                        }
                        else
                        {
                            _dutSender.SendData(ack, ipEndPiont);
                        }
                        //AppendLogToUi("-->发送老化时间", LOG_TYPE.INFO);
                    }
                    else if (cmdId == DutProtocol.SLAVE_CMD_PWR_KEY_SET)
                    {
                        ushort startSec = 0;
                        ushort spanMsec = 0;

                        //AppendLogToUi("-->设备请求设置唤醒", LOG_TYPE.INFO);
                        if (_lastCmd != cmdId)
                        {
                            PostEventAsync(DutEvent_I.EVT_SLAVE_EXEC_CMD, cmdId);
                            if (DutProtocol.DecodePwrKeySetPackage(decodeData, ref startSec, ref spanMsec))
                            {
                                powerSet.startSec = startSec;
                                powerSet.spanMsec = spanMsec;
                                OnPostEventAsyncToTeam(DutEvent_E.DUT_EVT_SET_PWR_KEY, _instanceId);
                                _dutSender.SendData(ack, ipEndPiont);
                                _lastCmd = cmdId;
                            }
                            else
                            {
                                Hlog.W(Mod, "Invalid recv  PWR_KEY_SET package.");
                            }
                        }
                        else
                        {
                            _dutSender.SendData(ack, ipEndPiont);
                            Hlog.W(Mod, "repeat cmd data:" + _lastCmd);
                        }

                        //PostEventAsync(DutEvent_I.EVT_SLAVE_READY);
                    }
                    else if (cmdId == DutProtocol.SLAVE_CMD_REPORT_RET)
                    {
                        // string errorData = Tools.HexToString(decodeData);
                        ushort status = DutProtocol.ParseStatus(decodeData);
                        //AppendLogToUi("-->设备上报结果", LOG_TYPE.INFO);
                        if (status == DutProtocol.STATUS_INVALID)
                        {
                            Hlog.W(Mod, "invalid status:" + status);
                            return false;
                        }
                        _dutSender.SendData(ack, ipEndPiont);
                        if (_lastCmd == cmdId)
                        {
                            Hlog.W(Mod, "repeat cmd:" + cmdId);
                            return true;
                        }
                        _lastCmd = cmdId;
                        if (status == DutProtocol.STATUS_PASS)
                        {
                            _statusCode = status;
                            PostEventAsync(DutEvent_I.EVT_SLAVE_TEST_FAIL1);
                        }
                        else
                        {
                            _statusCode = status;
                            PostEventAsync(DutEvent_I.EVT_SLAVE_TEST_FAIL2);
                        }
                        // Hlog.I(MOD_ID, "recv ret:" + errorData);
                    }
                    else if (cmdId == DutProtocol.SLAVE_CMD_RECORD_DATA)
                    {
                        RecordHead head = new RecordHead();
                        _lastCmd = cmdId;
                        string recvData = Tools.HexToString(decodeData);
                        Hlog.I(Mod, "recv record data:" + recvData);
                        //AppendLogToUi("-->设备保存信息:" + recvData, LOG_TYPE.INFO);
                        if (DutProtocol.ReadRecordDataHead(decodeData, decodeData.Length, ref head))
                        {
                            _dutSender.SendData(ack, ipEndPiont);
                            if (head.instanceId == _dutRecordLastId)
                            {
                                return true;
                            }
                            PostEventAsync(DutEvent_I.EVT_SLAVE_EXEC_CMD, cmdId);
                            _dutRecordLastId = head.instanceId;
                            if (head.dataType == (byte)DutProtocol.DataType.DT_STRING)
                            {
                                string content = "";
                                if (DutProtocol.ParseRecordData(decodeData, decodeData.Length, head, out content))
                                {
                                    _testInfoCSV.AddOneRecord(_recordInstance, content);
                                }
                            }
                            else if (head.dataType == (byte)DutProtocol.DataType.DT_UBYTE)
                            {
                                byte[] byteData = null;
                                if (DutProtocol.ParseRecordData(decodeData, decodeData.Length, head, out byteData))
                                {
                                    foreach (var v in byteData)
                                    {
                                        _testInfoCSV.AddOneRecord(_recordInstance, v);
                                    }
                                }
                            }
                            else if (head.dataType == (byte)DutProtocol.DataType.DT_USHORT)
                            {
                                ushort[] ushortData = null;
                                if (DutProtocol.ParseRecordData(decodeData, decodeData.Length, head, out ushortData))
                                {
                                    foreach (var v in ushortData)
                                    {
                                        _testInfoCSV.AddOneRecord(_recordInstance, v);
                                    }
                                }
                            }
                            else if (head.dataType == (byte)DutProtocol.DataType.DT_UINT)
                            {
                                UInt32[] uint32Data = null;
                                if (DutProtocol.ParseRecordData(decodeData, decodeData.Length, head, out uint32Data))
                                {
                                    foreach (var v in uint32Data)
                                    {
                                        _testInfoCSV.AddOneRecord(_recordInstance, v);
                                    }
                                }
                            }
                        }

                        //  Hlog.I(MOD_ID, "recv record data len:" + decodeData.Length);
                    }
                    else if (cmdId == DutProtocol.SLAVE_CMD_TEST_DONE)
                    {
                        //AppendLogToUi("-->设备测试成功", LOG_TYPE.INFO);
                        // 只在ST_TEST_START状态下才接受测试完成指令，防止上一轮残留报文触发误判
                        if (CurState != DutStatus.ST_TEST_START)
                        {
                            Hlog.W(Mod, "SLAVE_CMD_TEST_DONE in unexpected state:" + CurState);
                            _dutSender.SendData(ack, ipEndPiont);
                            return true;
                        }
                        if (_lastCmd == cmdId)
                        {
                            Hlog.W(Mod, "repeat SLAVE_CMD_TEST_DONE");
                            _dutSender.SendData(ack, ipEndPiont);
                            return true;
                        }
                        ushort status = DutProtocol.ParseStatus(decodeData);
                        _lastCmd = cmdId;
                        if (status == DutProtocol.STATUS_PASS)
                        {
                            _statusCode = status;
                            PostEventAsync(DutEvent_I.EVT_SLAVE_TEST_OK);
                            _dutSender.SendData(ack, ipEndPiont);
                        }
                    }
                    else if (cmdId == DutProtocol.MASTER_CMD_START_TEST)// ack cmd
                    {
                        if (_lastCmd == cmdId)
                        {
                            Hlog.W(Mod, "repeat MASTER_CMD_START_TEST");
                            _dutSender.SendData(ack, ipEndPiont);
                            return true;
                        }
                        ushort status = DutProtocol.ParseStatus(decodeData);
                        _lastCmd = cmdId;
                        if (status == DutProtocol.STATUS_PASS)
                        {
                            PostEventAsync(DutEvent_I.EVT_SLAVE_START_ACK);
                        }
                        else
                        {
                            Hlog.E(Mod, "start Ack  error status:" + status);
                        }
                        // AppendLogToUi("-->设备接收到参数开始测试", LOG_TYPE.INFO);
                    }
                    else // 未知的指令一律回复ack
                    {
                        _lastCmd = cmdId;
                        _dutSender.SendData(ack, ipEndPiont);
                        Hlog.W(Mod, "unhandle cmd_id:" + cmdId);
                        return true;
                    }
                }
                else
                {
                    Hlog.E(Mod, "Parse faile:" + error);
                    return false;
                }
            }
            return true;
        }
        public void OnConfigChange()
        {
            //Console.WriteLine(@"[{0}]:OnConfigChange", _instanceId);
            Hlog.I(Mod, "OnConfigChange");
        }
        /// <summary>
        /// 启动测试
        /// </summary>
        /// <param name="timeStamp">启动时间</param>
        /// <param name="temp">温度</param>
        /// <param name="tempReady">温度是否OK</param>
        public void ExcuteOnceTest(UInt32 timeStamp,TestBoardConfig config, float temp, bool tempReady, bool tempMainBoardError = false)
        {
            _statusCode = StateCode.SCODE_INVALID;
            _teamStartTimestamp = timeStamp;
			_testBoardCfg = config;
            _teampCtrMainBoardError = tempMainBoardError;
            _testTemp = temp;
            PostEventAsync(DutEvent_I.EVT_EXCUTE_TEST, tempReady);
        }
        public void ExcuteTimeout()
        {
            PostEventAsync(DutEvent_I.EVT_SLAVE_TEST_TIMEOUT, 0);
        }
        /// <summary>
        /// 测试板连接超时
        /// </summary>
        public void ExcuteConnTimeout()
        {
            PostEventAsync(DutEvent_I.EVT_SLAVE_TEST_TIMEOUT, StateCode.SCODE_DUT_CONN_TIMEOUT);
        }
        /// <summary>
        /// 通讯板通讯超时
        /// </summary>
        public void ExcuteTBCommunicateTimeout()
        {
            PostEventAsync(DutEvent_I.EVT_SLAVE_TEST_TIMEOUT, StateCode.SCODE_TB_COMMUNICATE_ERROR);
        }
        /// <summary>
        /// 温控板故障
        /// </summary>
        public void ExcuteTempCtrBoardAbnormal()
        {
            PostEventAsync(DutEvent_I.EVT_SLAVE_TEST_TIMEOUT, StateCode.SCODE_TEMP_MAIN_ERROR);
        }
        public void TriggerFaileType()
        {
            _statusCode = StateCode.SCODE_RUNIN_FAILE;
            PostEventAsync(DutEvent_I.EVT_SLAVE_TEST_FAIL2);
        }
        //public void OpenConnect()
        //{
        //   // PostEventAsync(DutEvent_I.EVT_START_CONN);
        //}


        public void CancelTestWork()
        {
            PostEventAsync(DutEvent_I.EVT_CANCEL_TASK);
        }

        /// <summary>
        /// 用于测试结束时恢复到等待测试状态
        /// </summary>
        public void ResetWorkStatus()
        {
            _statusCode = StateCode.SCODE_INVALID;
            _teampCtrMainBoardError = false;
            _stageInfo = "None";
            _repeatInfo = "None";
            _taskSerialNo = "--";
            PostEventAsync(DutEvent_I.EVT_RESET_STATUS);
        }
        /// <summary>
        /// 用于测试结束时恢复到等待测试状态
        /// </summary>
        public void SetTempError(float tempValue, bool tempMainBoardError = false)
        {
            _teampCtrMainBoardError = tempMainBoardError;
            PostEventAsync(DutEvent_I.EVT_TEMP_ASSERT, tempValue);
        }
        public void Destory()
        {
            StopTimeoutRetry();
            try
            {
                _dutSender.Close();
            }
            catch
            {

            }
            Stop(DutEvent_I.EVT_DESTORY, null);
        }

        public byte GetErrorCode()
        {
            return _errCode;
        }
        // 获取异常状态码StateCode
        public ushort GetAbnormalStatusCode()
        {
            if (_errCode == ERR_CODE_FAIL1 || _errCode == ERR_CODE_FAIL2 || _errCode == ERR_CODE_TIMEOUT)
            {
                if (_statusCode < StateCode.SCODE_RESERVE_MIN) //转换失败的状态码。
                {
                    return StateCode.SCODE_FUN_FAIL;
                }
            }
            return _statusCode;
        }

        public float GetLastEnvTemp()
        {
            return _testTemp;
        }
        public ushort GetStatusCode()
        {
            return _statusCode;
        }

        public string GetTestTime()
        {
            return Tools.TimeSpanToString(_testTime);
        }

        public string GetTestInfor()
        {
            return _testInfor;
        }

        public bool TestIsStarted()
        {
            return _bTestStart;
        }
        public void SaveTestResult()
        {
            if (CurState == DutStatus.ST_TEST_END)
            {
                PostEventAsync(DutEvent_I.EVT_SAVE_RESULT);
            }
        }

        public void SetExtraInfo(string stageInfo, string repeatInfo, string taskSerialNo)
        {
            _stageInfo = stageInfo;
            _taskSerialNo = taskSerialNo;
            _repeatInfo = repeatInfo;
        }


        public bool IsFreeMode()
        {
            if (CurState == DutStatus.ST_READY)
            {
                return true;
            }
            return false;
        }
        /// <summary>
        /// 生成总结性记录，用于复测模式最后写入记录
        /// </summary>
        /// <param name="recordObj"></param>
        /// <param name="passCount"></param>
        /// <param name="faileCount"></param>
        /// <param name="errCode"> 每个的errCode</param>
        /// 
        //public void SaveRetryTaskFixedRecord(UInt32 recordInstance ,CSVRecord recordObj, DateTime startTime, 
        //                                    /*UInt32 passCount, UInt32 faileCount,*/ byte errCode)
        //{
        //    //UInt32 recordInstance = recordObj.StartOneRecord();
        //    byte binCode = _binCodeManager.DefaultBin;
        //    TimeSpan testTime = DateTime.Now - startTime;
        //    _binCodeManager.GetBinNumber(errCode, ref binCode);
        //    if (recordInstance != CSVRecord.INVALID_INSTANCE_ID)
        //    {
        //        recordObj.AddFixedRecord(recordInstance, startTime.ToString("yyyy-MM-dd HH:mm:ss"));
        //        recordObj.AddFixedRecord(recordInstance, 0);
        //        recordObj.AddFixedRecord(recordInstance, "team" + (_teamIndex + 1).ToString());
                
        //     //   recordObj.AddFixedRecord(recordInstance, "board" + (_groupId + 1).ToString()); //  只有一个通信板的时候不记录
        //        recordObj.AddFixedRecord(recordInstance, "dut" + (_instanceId + 1).ToString());

        //        recordObj.AddFixedRecord(recordInstance, _testBoardSW);
        //        recordObj.AddFixedRecord(recordInstance, Tools.TimeSpanToString(testTime));
        //        recordObj.AddFixedRecord(recordInstance, binCode);
        //       // recordObj.AddFixedRecord(recordInstance, _testTemp.ToString());

        //        string resultDescription = GetResultDescript(errCode);
        //        recordObj.AddFixedRecord(recordInstance, resultDescription);
        //        recordObj.AddFixedRecord(recordInstance, errCode);
        //        //recordObj.AddFixedRecord(recordInstance, $"P/F:{passCount}/{faileCount}");
        //        //recordObj.AddFixedRecord(recordInstance, _extraInfo);
        //    }
           // recordObj.SaveRecord(recordInstance, true);
        //}
    }
}
