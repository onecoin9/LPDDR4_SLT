using Hsg.BLL.config;
using Hsg.BLL.Net;
using Hsg.Common;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace Hsg.BLL.TempCtr
{
    public enum TempCtrRet
    {
        ok,
        connect_fail,
        send_faile,
    }
    public class TempCtrBoardClient
    {
        private TempCtrBoardConfig _config;
        private TcpClientConn _tcpClient;
        public bool Connected = false;
        private readonly object _stateLock = new object();
        private const int RECV_BUF_SIZE = 256;
        private byte[] _respTmpBuf;
        private int _recvLen;
        private short _lastCmd = 0;
        private Semaphore _sendSem;
        private Action<short, byte[]> _onResponse;
        public float[] TmpCompensators { get { return _compensatorValue; } }
        private float[] _compensatorValue;//温度补偿
        public TempCtrBoardClient(TempCtrBoardConfig cfg, Action<short, byte[]> onResPonse)
        {
            _config = cfg;
            _recvLen = 0;
            _respTmpBuf = new byte[RECV_BUF_SIZE];
            _tcpClient = new TcpClientConn(OnRecvDataHandle, OnStateChange);
            _onResponse += onResPonse;
            _sendSem = new Semaphore(1, 1);
            _compensatorValue = new float[TempProtocol.ONE_TEAM_DUT_NUM];
        }
        public void StartConn()
        {
            _tcpClient.OpenConn(_config.IP, _config.Ports);
            //_tcpClient.OpenConn(
        }
        private void StopConn()
        {
            _tcpClient.CloseConn();
        }
        private void OnStateChange(bool isConn)
        {
            Connected = isConn;
        }


        private bool OnRecvDataHandle(byte[] data)
        {
            short cmdId = 0;
            byte[] param = new byte[0];
            int decodePos = 0;
            bool ret = false;
            if (data == null || data.Length == 0)
            {
                return false; // 如果数据为空或长度为0，直接返回false
            }
            lock (_stateLock)
            {
                if (data.Length + _recvLen <= RECV_BUF_SIZE)
                {
                    Array.Copy(data, 0, _respTmpBuf, _recvLen, data.Length);
                    _recvLen += data.Length;
                }
                else
                {
                    int copyLen = data.Length > RECV_BUF_SIZE ? RECV_BUF_SIZE : data.Length;
                    Array.Copy(data, 0, _respTmpBuf, 0, copyLen);
                    _recvLen = copyLen;
                }
            }

            //Console.WriteLine("recv:" + Tools.HexToString(data));

            do
            {
                ret = TempProtocol.DecodePackage(_respTmpBuf, _recvLen, ref decodePos, ref cmdId, ref param);
                if (ret)
                {
                    if (_lastCmd == cmdId)
                    {
                        _onResponse(cmdId, param);
                        // 尝试获取信号量  
                        _sendSem.WaitOne(0);
                        try
                        {
                            _sendSem.Release();
                        }
                        catch (Exception e)
                        {
                            Console.WriteLine($"_sendSem {e.Message}");
                        }
                    }
                }
                int remainingDataLength = _recvLen - decodePos;
                if (remainingDataLength > 0)
                {
                    Array.Copy(_respTmpBuf, decodePos, _respTmpBuf, 0, remainingDataLength);
                    _recvLen = remainingDataLength;
                }
                else
                {
                    _recvLen = 0;
                    Array.Clear(_respTmpBuf, 0, _respTmpBuf.Length);
                }
                
                //Hlog.W("recv:"+ $"rsp id:{cmdId} {_lastCmd} data:" + Tools.HexToString(data));
            } while (ret);
            return true;
        }

        private TempCtrRet SendCommand(short cmdId, byte[] param)
        {
            // int retry = 0;
            byte[] data = TempProtocol.EncodePackage(cmdId, param);
            // Console.WriteLine("send:" + Tools.HexToString(data));
            // 尝试获取信号量  
            _sendSem.WaitOne(1000);
            lock (_stateLock)
            {
                _lastCmd = cmdId;
                _recvLen = 0;
            }
            if (_tcpClient.SendData(data, data.Length))
            {
                return TempCtrRet.ok;
            }
            return TempCtrRet.send_faile;

        }


        //private TempCtrRet SendCommand(short cmdId, byte[] param, byte []response)
        //{
        //    int retry = 0;
        //    byte[] data = TempProtocol.EncodePackage(cmdId, param);
        //    // Console.WriteLine("send:" + Tools.HexToString(data));
        //    _lastCmd = cmdId;
        //    _recvLen = 0;
        //    _recvSem.WaitOne(0);
        //    while (!_tcpClient.SendData(data, data.Length))
        //    {
        //        if (retry < 3)
        //        {
        //            retry++;
        //            Task.Delay(500);
        //            //  Console.WriteLine("snd retry");
        //        }
        //        else
        //        {
        //            return TempCtrRet.send_faile;
        //        }
        //    }
        //    if(WaitForSemaphore(_recvSem, 3000))
        //    {

        //    }
        //    return TempCtrRet.ok;
        //}

        /// <summary>
        /// 查询温度
        /// </summary>
        /// <returns></returns>
        public TempCtrRet UpdateTemp()
        {
            if (Connected)
            {
                return SendCommand(TempProtocol.CMD_QUERY_TEMP, null);
            }
            return TempCtrRet.connect_fail;
        }


        /// <summary>
        /// 查询转速
        /// </summary>
        /// <returns></returns>
        public TempCtrRet UpdateFanSpeed()
        {
            if (Connected)
            {
                return SendCommand(TempProtocol.CMD_QUERY_FAN_SPEED, null);
            }
            return TempCtrRet.connect_fail;
        }

        /// <summary>
        /// 查询转速
        /// </summary>
        /// <returns></returns>
        public TempCtrRet QueryFault()
        {
            if (Connected)
            {
                return SendCommand(TempProtocol.CMD_QUERY_FAULT, null);
            }
            return TempCtrRet.connect_fail;
        }
        public TempCtrRet QueryVoltage()
        {
            if (Connected)
            {
                return SendCommand(TempProtocol.CMD_QUERY_VOLTAGE, null);
            }
            return TempCtrRet.connect_fail;
        }
        /// <summary>
        /// 开启温控
        /// </summary>
        /// <returns></returns>
        public TempCtrRet SwitchOnTempCtr()
        {
            if (Connected)
            {
                byte[] param = new byte[1];
                param[0] = TempProtocol.TEMP_SWITCH_ON;
                Array.Clear(_compensatorValue, 0, _compensatorValue.Length);
                return SendCommand(TempProtocol.CMD_ON_OFF, param);
            }
            return TempCtrRet.connect_fail;
        }

        public TempCtrRet SwitchOffTempCtr()
        {
            if (Connected)
            {
                byte[] param = new byte[1];
                param[0] = TempProtocol.TEMP_SWITCH_OFF;
                return SendCommand(TempProtocol.CMD_ON_OFF, param);
            }
            return TempCtrRet.connect_fail;
        }
        public void CancelResponse()
        {
            _lastCmd = 0;
        }
        public TempCtrRet SetTemp(float tempValue, float compensatorValue = 0)
        {
            if (Connected)
            {
                for (int i = 0; i < _compensatorValue.Length; i++)
                {
                    _compensatorValue[i] = compensatorValue;
                }
                short value = TempProtocol.EncodeSetTempParam(tempValue + compensatorValue);
                return SendCommand(TempProtocol.CMD_SET_TEMP, BitConverter.GetBytes(value));
            }
            return TempCtrRet.connect_fail;
        }
        public TempCtrRet SetTemp(float tempValue, float[] compensatorValues, bool [] hightTempEnableFlags)
        {
            if (Connected)
            {
                short[] setValue = new short[TempProtocol.ONE_TEAM_DUT_NUM];
                for (int i = 0; i < setValue.Length; i++)
                {
                    if(hightTempEnableFlags[i])
                    {
                        setValue[i] = TempProtocol.EncodeSetTempParam(tempValue + compensatorValues[i]);
                    }
                    else
                    {
                        setValue[i] = 0;
                    }
                    _compensatorValue[i] = compensatorValues[i];
                }
                byte[] byteValue = new byte[setValue.Length * 2];
                Buffer.BlockCopy(setValue, 0, byteValue, 0, byteValue.Length);
                return SendCommand(TempProtocol.CMD_SET_TEMP_DETAIL, byteValue);
            }
            return TempCtrRet.connect_fail;
        }

        public TempCtrRet SetFanSpeed(short speed)
        {
            if (Connected)
            {
                byte[] param = BitConverter.GetBytes(speed);
                return SendCommand(TempProtocol.CMD_SET_FAN_SPEED, param);
            }
            return TempCtrRet.connect_fail;
        }

        public TempCtrRet Set5VOnOff(bool enable)
        {
            if (Connected)
            {
                byte[] param = new byte[1];
                if (enable)
                {
                    param[0] = 1;
                }
                else
                {
                    param[0] = 0;
                }
                return SendCommand(TempProtocol.CMD_SET_VOLTAGE, param);
            }
            return TempCtrRet.connect_fail;
        }
    }
}
