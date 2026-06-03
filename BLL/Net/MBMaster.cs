using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

using System.Net;
using System.Net.Sockets;


using ModbusLib;
using ModbusLib.Protocols;
using Hsg.Common;
using Hsg.BLL.config;
using System.Threading;

namespace Hsg.BLL
{
    public class MBMaster
    {
        private int _transactionId;
        private ModbusClient _driver;
        private ICommClient _portClient;
        protected Socket _socket;
        private byte _lastReadCommand = 0;
        private AutoResetEvent _opLock = new AutoResetEvent(true);
        private ushort _startAddress;
        private ushort _dataLength;
        public const int REGIST_BUF_SIZE = 64;
        protected ushort[] _registerTemp;
        //private Action<string> _outputToUI;
        private MBConfig _mbConfig;
        private static readonly object _socketLock = new object();
        public MBMaster()
        {
            _registerTemp = new ushort[REGIST_BUF_SIZE];
        }
        //public MBMaster(Action<string> outPutToUI)
        //{
        //    _registerTemp = new ushort[REGIST_BUF_SIZE];
        //    _outputToUI = outPutToUI;
        //}
        protected void DriverOutgoingData(byte[] data)
        {
            // if (_logPaused)
            //    return;
            //var hex = new StringBuilder(data.Length * 2);
            //foreach (byte b in data)
            //    hex.AppendFormat("{0:x2} ", b);
            //if (_outputToUI != null)
            //{
            //    _outputToUI(String.Format("TX[{0}]: {1}", data.Length, hex));
            //}
            //AppendLog(String.Format("TX: {0}", hex));
            //Console.WriteLine("send" + hex);
        }
        protected void DriverIncommingData(byte[] data, int len)
        {
            //if (_logPaused)
            //   return;

            //var hex = new StringBuilder(len);
            //for (int i = 0; i < len; i++)
            //{
            //    hex.AppendFormat("{0:X2} ", data[i]);
            //}
            //if (_outputToUI != null)
            //{
            //    _outputToUI(String.Format("RX[{0}]: {1}", len, hex));
            //}
            //  AppendLog(String.Format("RX: {0}", hex));
            //Console.WriteLine("recv" + hex);

        }

        protected void AppendLog(String log)
        {
            Console.WriteLine(log);
            Hlog.E("MBMaster:" + log);
        }

        private bool ExecuteReadCommand(byte function)
        {
            bool ret = false;
            _lastReadCommand = function;

            try
            {
                CommResponse result;
                var command = new ModbusCommand(function) { Offset = _startAddress, Count = _dataLength, TransId = _transactionId++ };
                if (_portClient == null)
                {
                    CreateConnect();
                }
                if (_portClient != null)
                {
                    result = _driver.ExecuteGeneric(_portClient, command);


                    if (result.Status == CommResponse.Ack)
                    {
                        //command.Data.CopyTo(_registerData, _startAddress);
                        command.Data.CopyTo(_registerTemp, 0);
                        ret = true;
                        AppendLog(String.Format("Read succeeded: Function code:{0}.", function));
                    }
                    else
                    {
                        AppendLog(String.Format("Failed to execute Read: Error code:{0}", result.Status));
                        if(result.Status == CommResponse.Critical) // 通信可能存在问题
                        {
                           ReleaseConnect();
                        }
                    }
                }
                else
                {
                    AppendLog("_portClient != null");
                }
            }
            catch (Exception ex)
            {
                AppendLog("ReadCommand err:" + ex.Message);
            }
            return ret;
        }

        private bool ExecuteWriteCommand(byte function)
        {
            try
            {
                var command = new ModbusCommand(function)
                {
                    Offset = _startAddress,
                    Count = _dataLength,
                    TransId = _transactionId++,
                    Data = new ushort[_dataLength]
                };
                for (int i = 0; i < _dataLength; i++)
                {
                    command.Data[i] = _registerTemp[i];
                }
                CommResponse result;
                if (_portClient == null)
                {
                    CreateConnect();
                }
                if (_portClient != null)
                {
                    result = _driver.ExecuteGeneric(_portClient, command);

                    if (result.Status == CommResponse.Ack)
                    {
                        return true;
                    }
                    else
                    {
                        AppendLog(result.Status == CommResponse.Ack
                             ? String.Format("Write succeeded: Function code:{0}", function)
                             : String.Format("Failed to execute Write: Error code:{0}", result.Status));
                        if (result.Status == CommResponse.Critical) // 通信可能存在问题
                        {
                            ReleaseConnect();
                        }
                    }
                }
                else
                {
                    AppendLog("conn not ready");
                }

                return false;
            }
            catch (Exception ex)
            {
                AppendLog("write cmd assert:" + ex.Message);
                return false;
            }
        }

        public bool WriteMultipleReg(ushort startReg, ushort[] data)
        {
            if (data.Length > REGIST_BUF_SIZE)
            {
                AppendLog("Data length exceeds buffer size.");
                return false;
            }

            _startAddress = startReg;
            _dataLength = (ushort)data.Length;
            data.CopyTo(_registerTemp, 0);
            return ExecuteWriteCommand(ModbusCommand.FuncWriteMultipleRegisters);
        }

        public bool ReadMultipleReq(ushort startReg, UInt16 dataLen, ushort[] outData)
        {
            bool ret = false;
            _startAddress = startReg;
            _dataLength = dataLen;
            ret = ExecuteReadCommand(ModbusCommand.FuncReadMultipleRegisters);
            Array.Copy(_registerTemp, outData, 2);
            return ret;
        }

        public bool StartConnect(MBConfig config)
        {
            _mbConfig = config;
            try
            {
                _driver = new ModbusClient(new ModbusRtuCodec()) { Address = config.slaveId };
                //_driver.OutgoingData += DriverOutgoingData;
                //_driver.IncommingData += DriverIncommingData;
                return CreateConnect();
            }
            catch (Exception ex)
            {
                AppendLog($"Error: {ex.Message}\nStack Trace: {ex.StackTrace}");
                DoDisconnect();
                ReleaseConnect();
                return false;
            }
        }
        private bool CreateConnect()
        {

            try
            {
                lock (_socketLock)
                {
                    _socket = new Socket(AddressFamily.InterNetwork, SocketType.Dgram, ProtocolType.Udp);
                    _socket.Bind(new IPEndPoint(IPAddress.Any, 0));
                    _socket.Connect(new IPEndPoint(IPAddress.Parse(_mbConfig.ipAddr), _mbConfig.remotePort));
                    _portClient = _socket.GetClient();
                }
                return true;
            }
            catch (Exception ex)
            {
                AppendLog($"Error: {ex.Message}\nStack Trace: {ex.StackTrace}");
                ReleaseConnect();
                return false;
            }
        }
        private void ReleaseConnect()
        {
            lock (_socketLock)
            {
                _portClient = null;
                if (_socket != null)
                {
                    try
                    {
                        _socket.Close();
                        _socket.Dispose();
                        _socket = null;
                    }
                    catch (Exception ex)
                    {
                        AppendLog($"Error: {ex.Message}\nStack Trace: {ex.StackTrace}");
                    }
                }
            }
        }

        public void DoDisconnect()
        {
            _driver = null;
            ReleaseConnect();
        }
    }
}
