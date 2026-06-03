using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.IO;
using System.Text.RegularExpressions;
using System.Runtime.InteropServices;
using Hsg.Common;

namespace Hsg.BLL
{

    struct TestInfor
    {
        public byte totalCapacity;// Gbit
        public byte rank0Capacity;//Gbit
        public byte rank0Die;//
        public byte rank1Capacity;//Gbit
        public byte rank1Die;//
        public bool DecodeInfor(byte[] data, int size, ref string infor)
        {
            if (size == Marshal.SizeOf(this))
            {
                totalCapacity = data[0];
                rank0Capacity = data[1];
                rank0Die = data[2];
                rank1Capacity = data[3];
                rank1Die = data[4];
                infor = string.Format("容量:{0}Gb\rRank0:{1}Gb,{2}Die\rRank1:{3}Gb,{4}Die",
                   totalCapacity, rank0Capacity, rank0Die, rank1Capacity, rank1Die);
                return true;
            }
            return false;
        }
    }

    struct StartReadyInfor
    {
        public ushort apHWCode;
        public ushort apHWSubCode;
        public ushort apHWVer;
        public ushort apSWVer;
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 4)]
        public byte[] sfData;
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 4)]
        public byte[] sfVer;

        public bool DecodeInfor(byte[] data, int size)
        {
            sfData = new byte[4];
            sfVer = new byte[4];
            if (size != Marshal.SizeOf(this))
            {
                Hlog.I("DecodeInfor", "size:" + size + "!= " + Marshal.SizeOf(this));
                return false;
            }
            apHWCode = (ushort)(data[0] | data[1] << 8);
            apHWSubCode = (ushort)(data[2] | data[3] << 8);
            apHWVer = (ushort)(data[4] | data[5] << 8);
            apSWVer = (ushort)(data[6] | data[7] << 8);

            sfData[0] = data[8];
            sfData[1] = data[9];
            sfData[2] = data[10];
            sfData[3] = data[11];

            sfVer[0] = data[12];
            sfVer[1] = data[13];
            sfVer[2] = data[14];
            sfVer[3] = data[15];
            return true;
        }
    }

    public struct RecordHead
    {
        public byte instanceId;
        public byte dataType;
    };
    public class DutProtocol
    {
        public enum DataType
        {
            DT_STRING = 0x00,
            DT_UBYTE = 0x01,
            DT_USHORT = 0x02,
            DT_UINT = 0x04,
            DT_INVALID = 0xff
        };

        // 通讯命令
        // TB -->PC
        public const byte SLAVE_CMD_READY = 0x10;
        public const byte SLAVE_CMD_TEST_INFO = 0x11;// 读取存储容量，rank ,die 等信息
        public const byte SLAVE_CMD_AGING_TIME = 0x12;// 用于传输配置文件里面的睡眠时间，暂时废弃
        public const byte SLAVE_CMD_PWR_KEY_SET = 0x13;// 用于设置请求唤醒的时间，用于外部唤醒

        /// <summary>
        /// 上报测试问题
        /// </summary>
        public const byte SLAVE_CMD_REPORT_RET = 0x16;
        public const byte SLAVE_CMD_TEST_DONE = 0x17;
        public const byte SLAVE_CMD_RECORD_DATA = 0x18;// 用于记录测试信息
        private static byte[] _ConfigData = new byte[1];

        // const byte CMD_LOAD_CONFIG = 0x11;
        // PC -->TB
        public const byte MASTER_CMD_START_TEST = 0x15;

        //character id
        const byte SERVER_CHARACTER_ID = 0x00;
        const byte SLAVE_CHARACTER_ID = 0x01;
        const byte HEAD_BYTE = 0xAF;
        const byte TAIL_BYTE = 0xEF;
        // status code
        public const ushort STATUS_PASS = 0;
        public const ushort STATUS_CHECKSUM_ER = 0x01;
        public const ushort STATUS_SINGL_FAIL = 0x02;
        public const ushort STATUS_INVALID_SETTING = 0x03;
        public const ushort STATUS_INIT_FAIL = 0x04;
        public const ushort STATUS_INVALID = 0xFFFF;// invalid status code.
        public static ushort AgingTime = 0;// 老化时间，用于兼容旧版本早期软件

        public enum ErrorCode
        {
            ER_OK,
            ER_MEM,// 内存不足
            ER_FORMAT,// 数据格式错误
            ER_CHECKSUM// 数据格式错误
        }
        static private byte[] EncodeCmdPackage(byte cmdId, byte[] data)
        {
            int configLen = (data == null ? 0 : data.Length);

            byte[] encData = new byte[7 + configLen];
            ushort dataLen = (ushort)configLen;
            int i = 0;
            byte checkSum = 0x55;
            encData[i++] = HEAD_BYTE;
            encData[i++] = (byte)(dataLen & 0x00ff);
            encData[i++] = (byte)((dataLen & 0xff00) >> 8);
            encData[i++] = SERVER_CHARACTER_ID;
            encData[i++] = cmdId;

            if (configLen > 0)
            {
                foreach (byte v in data)
                {
                    encData[i++] = v;
                    checkSum ^= v;
                }
            }

            encData[i++] = checkSum;
            encData[i++] = TAIL_BYTE;
            return encData;
        }


        public static byte[] GenerateStartTestPackage(byte [] configData)
        {
            return EncodeCmdPackage(MASTER_CMD_START_TEST, configData);
        }

        public static byte[] GenerateAckPackage(byte cmdId, byte status)
        {
            byte[] encData = new byte[9];
            encData[0] = HEAD_BYTE;
            encData[1] = 0x02;
            encData[2] = 0x00;
            encData[3] = SERVER_CHARACTER_ID;
            encData[4] = cmdId;
            encData[6] = status;
            encData[7] = (byte)(0x55 ^ status);
            encData[8] = TAIL_BYTE;
            return encData;
        }

        public static byte[] GenerateAginTimeAckPackage(ushort aginTime)
        {
            byte[] encData = new byte[9];
            byte[] aginTimeByte = BitConverter.GetBytes(aginTime);
            encData[0] = HEAD_BYTE;
            encData[1] = 0x02;
            encData[2] = 0x00;
            encData[3] = SERVER_CHARACTER_ID;
            encData[4] = SLAVE_CMD_AGING_TIME;
            encData[5] = aginTimeByte[1];
            encData[6] = aginTimeByte[0];
            encData[7] = (byte)(0x55 ^ aginTimeByte[1] ^ aginTimeByte[0]);
            encData[8] = TAIL_BYTE;
            return encData;
        }

        public static ErrorCode DecodeCmdPackage(byte[] recvData, out byte cmdId, ref byte[] outData, out short dataLen)
        {
            dataLen = 0;
            cmdId = 0;

            if (recvData.Length < 7)
            {
                return ErrorCode.ER_FORMAT;
            }
            if (recvData[0] != HEAD_BYTE || recvData[3] != SLAVE_CHARACTER_ID)
            {
                return ErrorCode.ER_FORMAT;
            }
            dataLen = recvData[2];
            dataLen &= 0xff;
            dataLen <<= 8;
            dataLen += recvData[1];
            cmdId = recvData[4];
            if (dataLen + 7 > recvData.Length)
            {
                return ErrorCode.ER_FORMAT;
            }
            byte checkSum = 0x55;
            outData = new byte[dataLen];
            if (outData == null)
            {
                return ErrorCode.ER_MEM;
            }
            for (int i = 0; i < dataLen; i++)
            {
                outData[i] = recvData[i + 5];
                checkSum ^= outData[i];
            }
            if (checkSum != recvData[dataLen + 5])
            {
                return ErrorCode.ER_CHECKSUM;
            }
            return ErrorCode.ER_OK;
        }

        static public bool DecodePwrKeySetPackage(byte[] data, ref ushort startSecond, ref ushort spanMsec)
        {
            if (data.Length == 2)
            {
                startSecond = data[0];
                spanMsec = (ushort)(data[1]);// 单位为0.1s
                spanMsec *= 100;
                return true;
            }
            return false;
        }
        //static public bool LoadConfigFile(string confPath)
        //{
        //    bool ret = false;
        //    _ConfigData = null;
        //    if (confPath.Length == 0 || !File.Exists(confPath))
        //    {
        //        return false;
        //    }
        //    using (FileStream reader = File.OpenRead(confPath))
        //    {
        //        if (reader.Length > 0)
        //        {
        //            _ConfigData = new byte[reader.Length + 1];// add one byte as end of the content.
        //            reader.Read(_ConfigData, 0, (int)reader.Length);
        //            ret = true;
        //        }
        //        reader.Close();
        //    }
        //    String str = ASCIIEncoding.Default.GetString(_ConfigData);
        //    Match ma = Regex.Match(str, @"AgingTime=\d+");
        //    if (ma != null && ma.Value.Length > 0)
        //    {
        //        AgingTime = ushort.Parse(ma.Value.Substring(10));
        //    }
        //    return ret;
        //}

        static public bool LoadConfigBuf(byte[] sourceData)
        {
            _ConfigData = null;
            if (sourceData.Length == 0)
            {
                return false;
            }
            if (sourceData[sourceData.Length - 1] != 0)// 给内容最后面补0
            {
                _ConfigData = new byte[sourceData.Length + 1];
                Array.Copy(sourceData, _ConfigData, sourceData.Length);
            } else
            {
                _ConfigData = new byte[sourceData.Length];
                Array.Copy(sourceData, _ConfigData, sourceData.Length);
            }

            String str = ASCIIEncoding.Default.GetString(_ConfigData);
            Match ma = Regex.Match(str, @"AgingTime=\d+");
            if (ma != null && ma.Value.Length > 0)
            {
                AgingTime = ushort.Parse(ma.Value.Substring(10));
            }
            return true;
        }
        public static ushort ParseStatus(byte[] data)
        {
            ushort status = STATUS_INVALID;
            if (data.Length == 2)
            {
                status = 0;
                status |= data[1];
                status <<= 8;
                status |= data[0];
            }
            return status;
        }

        public static bool ParseStartReady(byte[] data, int len, ref string version)
        {
            StartReadyInfor testboardInfo = new StartReadyInfor();
            if (testboardInfo.DecodeInfor(data, len))
            {
                version = Encoding.ASCII.GetString(testboardInfo.sfData) + "_" + Encoding.ASCII.GetString(testboardInfo.sfVer);
                return true;
            }
            return false;
        }

        public static bool ParseTestInfor(byte[] data, int len, ref string inforStr)
        {
            if (len <= 0)
            {
                return false;
            }
            TestInfor infor = new TestInfor();
            return infor.DecodeInfor(data, len, ref inforStr);
        }

        public static bool ReadRecordDataHead(byte[] data, int len, ref RecordHead head)
        {
            if (len < Marshal.SizeOf(head))
            {
                return false;
            }
            head.instanceId = data[0];
            head.dataType = data[1];
            return true;
        }
        public static bool ParseRecordData(byte[] data, int len, RecordHead head, out string inforStr)
        {
            int startPos = Marshal.SizeOf(head);
            if (len <= 0 || len < startPos || head.dataType != (byte)DataType.DT_STRING)
            {
                inforStr = null;
                return false;
            }
            inforStr = Encoding.UTF8.GetString(data, startPos, len - startPos);
            return true;
        }

        public static bool ParseRecordData(byte[] data, int len, RecordHead head, out byte[] inforArray)
        {
            int startPos = 2;
            int count = (len - startPos) / 1;
            if (len <= 0 || head.dataType != (byte)DataType.DT_UBYTE || len < startPos || count <= 0)
            {
                inforArray = null;
                return false;
            }

            byte[] paseData = new byte[count];
            Array.Copy(data, startPos, paseData, 0, count);
            inforArray = paseData;
            return true;
        }

        public static bool ParseRecordData(byte[] data, int len, RecordHead head, out ushort[] inforArray)
        {
            int startPos = 2;
            int count = (len - startPos) / 2;
            if (len <= 0 || head.dataType != (byte)DataType.DT_USHORT || len < startPos || count <= 0)
            {
                inforArray = null;
                return false;
            }

            ushort[] paseData = new ushort[count];
            for (int i = 0; i < count; i++)
            {
                paseData[i] = BitConverter.ToUInt16(data, startPos);
                startPos += 2;
            }
            inforArray = paseData;
            return true;
        }

        public static bool ParseRecordData(byte[] data, int len, RecordHead head, out UInt32[] inforArray)
        {
            int startPos = 2;
            int count = (len - startPos) / 4;
            if (len <= 0 || head.dataType != (byte)DataType.DT_UINT || len < startPos || count <= 0)
            {
                inforArray = null;
                return false;
            }

            UInt32[] paseData = new UInt32[count];
            for (int i = 0; i < count; i++)
            {
                paseData[i] = BitConverter.ToUInt32(data, startPos);
                startPos += 4;
            }
            inforArray = paseData;
            return true;
        }

    }
}
