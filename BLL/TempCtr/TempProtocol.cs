using Hsg.Common;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Hsg.BLL.TempCtr
{
    /* package
    CmdFlag 命令标志    Uint32	4个字节
    CmdID   命令码 Uint16  2
    CmdDataSize 命令数据长度  Uint16	2
    CmdData 命令数据    Uint8 N
    CRC8 校验值 Uint8	1
    */
    public class TempProtocol
    {
        public const short CMD_QUERY_TEMP = 0x01;// 查询温度
        public const short CMD_QUERY_FAN_SPEED = 0x02; // 查询风扇转速
        public const short CMD_SET_TEMP = 0x03; // 设定温度（所有dut温度相同）
        public const short CMD_SET_FAN_SPEED = 0x04; // 设定风扇转速
        public const short CMD_ON_OFF = 0x05; // 开启关闭温控
        public const short CMD_QUERY_FAULT = 0x07;// 查询异常
        public const short CMD_QUERY_VOLTAGE = 0x08;// 查询电流异常
        public const short CMD_SET_VOLTAGE = 0x09;// 设置5V电压
        public const short CMD_SET_TEMP_DETAIL = 0x0B;// 设置每个dut 不同温度。
        private const UInt32 HEAD_WORD = 0x5A4B4457;

        public const int ONE_TEAM_DUT_NUM = 24; // 一个测试组里面有24个温控模块
        public const int ONE_TEAM_FAN_NUM = 4;// 一个测试组里面有4个风扇

        private const short TEMP_DEVIATION = 400;// 温度偏差负400（最低-40）

        public static byte STATE_CODE_OK = 0x01;

        public static int DETECT_VOL_CHANNEL_NUM = 3;// 有三路电压检测
        public static int POGO_PIN_NUM = 2; // 有2个pogo PIN ,每一个都有3路电压检测

        public static byte TEMP_SWITCH_ON = 0x01;
        public static byte TEMP_SWITCH_OFF = 0x00;

        private static byte GetCheckSum(byte[] data, int start, int end)
        {
            byte checkSum = 0;
            for (int i = start; i < end; i++)
            {
                checkSum += data[i];
            }
            return checkSum;
        }

        public static byte[] EncodePackage(short cmdId, byte[] param = null)
        {
            short paramLen = (short)(param == null ? 0 : param.Length);
            byte[] package = new byte[paramLen + 9];
            int start = 0;
            Array.Copy(BitConverter.GetBytes(HEAD_WORD), package, sizeof(UInt32));
            start += sizeof(UInt32);
            Array.Copy(BitConverter.GetBytes(cmdId), 0, package, start, sizeof(short));
            start += sizeof(short);
            Array.Copy(BitConverter.GetBytes(paramLen), 0, package, start, sizeof(short));
            start += sizeof(short);
            if (paramLen > 0)
            {
                Array.Copy(param, 0, package, start, paramLen);
                start += paramLen;
            }
            package[start] = GetCheckSum(package, 0, start);
            return package;
        }

        public static bool DecodePackage(byte[] package, int packageLen, ref int decodePos, ref short cmdId, ref byte[] param)
        {
            int headPos = 0;
            decodePos = 0;
            if (package == null || packageLen < 9)
            {
                return false; // 数据包长度不足，无法解析
            }

            int parseStart = 0;
            bool headerFound = false;

            // 循环查找头字节
            while (parseStart <= packageLen - sizeof(uint))
            {
                if(package[parseStart] == (byte)(HEAD_WORD&0xFF))
                {
                    uint headWord = BitConverter.ToUInt32(package, parseStart);
                    if (headWord == HEAD_WORD)
                    {
                        headerFound = true;
                        break; // 找到头字节
                    }
                }
                parseStart++; // 未找到头字节，继续查找
            }

            if (!headerFound)
            {
                decodePos = packageLen - sizeof(uint) + 1;
                return false; // 未找到头字节
            }

            // 检查数据包长度是否足够
            if (packageLen - parseStart < 9)
            {
                decodePos = parseStart;
                return false; // 数据包长度不足，无法解析
            }

            headPos = parseStart;
            // 解析命令ID
            parseStart += sizeof(uint);
            cmdId = BitConverter.ToInt16(package, parseStart);

            // 解析参数长度
            parseStart += sizeof(short);
            short paramLen = BitConverter.ToInt16(package, parseStart);

            if (paramLen + 9 > packageLen - headPos)
            {
                return false;
            }

          //  byte sourceSum = package[packageLen - 1 + headPos];
            byte sourceSum = package[headPos + 9 - 1+ paramLen];
            byte checkSum = GetCheckSum(package, headPos, headPos + paramLen + 8);// 9-1 last byte is checksum
            decodePos = headPos + paramLen + 9;
            if (sourceSum != checkSum)
            {
                Console.WriteLine("check sum err:" + checkSum.ToString("X2"));
                return false;
            }

            // 解析参数
            parseStart += sizeof(short);
            param = new byte[paramLen];
            if (paramLen > 0)
            {
                Array.Copy(package, parseStart, param, 0, paramLen);
            }
            return true;
        }



        public static bool DecodeTempParams(byte[] param, ref float[] tempValues, float[] compensatorValues)
        {
            Byte stateCode = 0;
            int parseStart = 0;
            int i = 0;
            if (param.Length != sizeof(short) * ONE_TEAM_DUT_NUM + 1)
            {
                return false;
            }
            tempValues = new float[ONE_TEAM_DUT_NUM];
            stateCode = param[0];
            if (stateCode != STATE_CODE_OK)
            {
                return false;
            }
            parseStart += 1;

            do
            {
                short temp = BitConverter.ToInt16(param, parseStart);
                temp -= TEMP_DEVIATION;
                parseStart += sizeof(short);
                tempValues[i] = (float)temp / 10 - compensatorValues[i];
                i++;
            } while (parseStart < param.Length);

            return true;
        }

        public static bool DecodeFanParams(byte[] param, ref ushort[] speedValues)
        {
            Byte stateCode = 0;
            int parseStart = 0;
            int i = 0;
            if (param.Length < sizeof(short) * ONE_TEAM_FAN_NUM + 1)
            {
                return false;
            }
            speedValues = new ushort[ONE_TEAM_FAN_NUM];
            stateCode = param[0];
            if (stateCode != STATE_CODE_OK)
            {
                return false;
            }
            parseStart += 1;
            byte[] fanBytes = new byte[sizeof(ushort)];
            do
            {
                fanBytes[0] = param[parseStart + 1];
                fanBytes[1] = param[parseStart];// 高字节在前
                speedValues[i] = BitConverter.ToUInt16(fanBytes, 0);
                parseStart += sizeof(short);
                i++;
            } while (parseStart < param.Length && i < ONE_TEAM_FAN_NUM);

            return true;
        }

        /// <summary>
        ///  解析故障码
        /// </summary>
        /// <param name="param"></param>
        /// <param name="tmpStates">温控板通讯故障码4byte</param>
        /// <param name="fanStates">风扇故障码4 byte</param>
        /// <returns></returns>
        public static bool DecodeQueryFaultParams(byte[] param, ref byte[] tmpStates, ref byte[] fanStates)
        {
            Byte stateCode = 0;
            int parseStart = 0;
            int i = 0;
            if (param.Length != sizeof(short) * ONE_TEAM_DUT_NUM + 1 + 4 + 4 + 4)
            {
                return false;
            }
            tmpStates = new byte[ONE_TEAM_DUT_NUM / 8];
            stateCode = param[0];
            if (stateCode != STATE_CODE_OK)
            {
                return false;
            }
            parseStart += 1;// state code
            parseStart += sizeof(short) * ONE_TEAM_DUT_NUM; // test bytes

            do
            {
                tmpStates[i] = param[parseStart];
                parseStart += 1;
                i++;
            } while (i < tmpStates.Length);
            parseStart += 1; // for byte keep align
            parseStart += 4;// for test

            fanStates = new byte[ONE_TEAM_FAN_NUM];
            Array.Copy(param, parseStart, fanStates, 0, fanStates.Length);
            return true;
        }

        public static bool DecodeVoltageParams(byte[] param,
                                                ref ushort[] detectVoltage,
                                                ref ushort[] shuntVol)
        {
            Byte stateCode = 0;
            int parseStart = 0;
            //int i = 0;
            if (param.Length < sizeof(short) * DETECT_VOL_CHANNEL_NUM * POGO_PIN_NUM * 2 + 1)
            {
                return false;
            }
            detectVoltage = new ushort[DETECT_VOL_CHANNEL_NUM * POGO_PIN_NUM];
            shuntVol = new ushort[DETECT_VOL_CHANNEL_NUM * POGO_PIN_NUM];
            stateCode = param[0];
            if (stateCode != STATE_CODE_OK)
            {
                return false;
            }
            parseStart += 1;
            byte[] volBytes = new byte[sizeof(ushort)];
            byte[] curBytes = new byte[sizeof(ushort)];
            int shutVolOffset = DETECT_VOL_CHANNEL_NUM * POGO_PIN_NUM * sizeof(short);
            for (int i = 0; i < POGO_PIN_NUM; i++)
            {
                for (int j = 0; j < DETECT_VOL_CHANNEL_NUM; j++)
                {
                    volBytes[0] = param[parseStart];
                    volBytes[1] = param[parseStart + 1];// 高字节在前
                    detectVoltage[i * DETECT_VOL_CHANNEL_NUM + j] = BitConverter.ToUInt16(volBytes, 0);
                    curBytes[0] = param[parseStart + shutVolOffset];
                    curBytes[1] = param[parseStart + 1 + shutVolOffset];// 高字节在前
                    shuntVol[i * DETECT_VOL_CHANNEL_NUM + j] = BitConverter.ToUInt16(curBytes, 0);
                    parseStart += sizeof(short);
                }
            }
            return true;
        }
        public static short EncodeSetTempParam(float temp)
        {
            short sTemp = (short)((temp * 10));
            // byte[] result = BitConverter.GetBytes(sTemp);
            return sTemp;
        }

        public static byte[] EncodeSetFanSpeedParam(short speed)
        {
            byte[] result = BitConverter.GetBytes(speed);
            return result;
        }

        public static byte[] EncodeSet5VOnOffParam(bool isOn)
        {
            byte[] result = new byte[1];
            if (isOn)
            {
                result[0] = 1;
            }
            else
            {
                result[0] = 0;
            }
            return result;
        }
    }
}
