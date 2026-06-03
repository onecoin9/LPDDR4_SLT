using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Hsg.BLL
{
    /// <summary>
    /// handler communicate protocol（帧解析部分，JSON 编解码见 HCProtocol.Json.cs）
    /// </summary>
    public partial class HCProtocol
    {
        public enum CmdId
        {
            CMD_INVALID,
            CMD_CHECK_READY,// 询问是否 Ready， 然后机械控制上料，然后开始测试 
            CMD_START,
            CMD_FINISH_ACK,
            CMD_SYNC_TMP_ACK,
            CMD_QUERY_DUT_ACK,
            CMD_ALARM_ACK,
        }
        public const byte ERROR_NONE = 0x00;  // 无错误
        public const Byte ERROR_MODE = 0x01; // 不在测试模式
        public const Byte ERROR_PARAM = 0x02; // 参数错误
        public const Byte ERROR_OTHER = 0x03; // 其他错误
        public const byte ERROR_WAIT = 0x04; // 继续等待


        private const string HEAD_START_TEST = "START_TEST ";
        private const string HEAD_START_ACK = "START_TEST_OK";
        private const string HEAD_FINISH_TEST = "TEST_DONE ";
        private const string HEAD_FINISH_ACK = "TEST_DONE_ACK";
        private const string HEAD_CHECK_READY = "CHECK_READY ";
        private const string HEAD_CHECK_ACK = "CHECK_ACK";
        private const string HEAD_SYNC_TEMP = "CFG_SYNC T";
        private const string HEAD_SYNC_ACK = "CFG_ACK";
        private const string HEAD_DUT_QUERY = "DUT_QUERY";
        private const string HEAD_DUT_QUERY_ACK = "DUT_SYNC_ACK";
        private const string HEAD_ALARM_REQ = "ALARM_REQ";
        private const string HEAD_ALARM_ACK = "ALARM_REQ_ACK";
        private const char BEGAIN_CHAR = '@';
        private const char END_CHAR = '+';
        static public CmdId DecodeRecvData(byte[] recvData, ref string outData, int startIndex, ref int decodeEnd)
        {
            string cmdBuff = ASCIIEncoding.Default.GetString(recvData);
            int begainPos = cmdBuff.IndexOf(BEGAIN_CHAR, startIndex);
            int endPos = cmdBuff.IndexOf(END_CHAR, startIndex);
            if (endPos > 0)
            {
                decodeEnd = endPos;
            }
            else // 长度不够下次解析
            {
                decodeEnd = startIndex;
                return CmdId.CMD_INVALID;
            }

            if (begainPos >= 0)
            {
                if (endPos + 1 > begainPos)
                {
                    string cmdStr = cmdBuff.Substring(begainPos + 1, endPos - begainPos - 1);
                    if (cmdStr.StartsWith(HEAD_START_TEST)) // START CMD
                    {
                        outData = cmdStr.Substring(HEAD_START_TEST.Length);
                        return CmdId.CMD_START;
                    }
                    else if (cmdStr.StartsWith(HEAD_CHECK_READY))
                    {
                        outData = cmdStr.Substring(HEAD_CHECK_READY.Length);
                        return CmdId.CMD_CHECK_READY;
                    }
                    else if (cmdBuff.IndexOf(HEAD_FINISH_ACK) >= 0)
                    {
                        outData = cmdStr.Substring(HEAD_FINISH_ACK.Length);
                        return CmdId.CMD_FINISH_ACK;
                    }
                    else if (cmdBuff.IndexOf(HEAD_SYNC_ACK) >= 0)
                    {
                        outData = cmdStr.Substring(HEAD_SYNC_ACK.Length);
                        return CmdId.CMD_SYNC_TMP_ACK;
                    }
                    else if (cmdBuff.IndexOf(HEAD_DUT_QUERY_ACK) >= 0)
                    {
                        outData = cmdStr.Substring(HEAD_DUT_QUERY_ACK.Length);
                        return CmdId.CMD_QUERY_DUT_ACK;
                    }
                    else if (cmdBuff.IndexOf(HEAD_ALARM_ACK) >= 0)
                    {
                        outData = cmdStr.Substring(HEAD_ALARM_ACK.Length);
                        return CmdId.CMD_ALARM_ACK;
                    }
                }
            }
            return CmdId.CMD_INVALID;
        }
        static public string EncodeTestDonePackage(int teamId, byte[] outFlag)
        {
            string package = BEGAIN_CHAR + HEAD_FINISH_TEST + teamId.ToString("D2") + " ";
            for (int i = 0; i < outFlag.GetLength(0); i++)
            {
                package += outFlag[i].ToString();
                if (i < outFlag.GetLength(0) - 1)
                {
                    package += " ";
                }
            }
            package += END_CHAR;
            return package;
        }

        static public string EncodeStartAck(int teamId)
        {
            string str = BEGAIN_CHAR + HEAD_START_ACK + " " + teamId.ToString("D2") + END_CHAR;
            return str;
        }

        static public string EncodeCheckReadyAck(int teamId, byte errorCode)
        {
            string str = "";
            str += BEGAIN_CHAR;
            str += HEAD_CHECK_ACK;
            str += " ";
            str += teamId.ToString("D2");
            str += " ";
            str += errorCode.ToString("D2");
            str += END_CHAR;
            return str;
        }

        static public string EncodeSyncTempRequest(byte tempFlag, string tempValue)
        {
            string str = "";
            str += BEGAIN_CHAR;
            str += HEAD_SYNC_TEMP;
            str += " ";
            str += tempFlag.ToString("D2");
            str += " ";
            str += tempValue;
            str += END_CHAR;
            return str;
        }

        static public string EncodeDutsStateRequest(int testTeam)
        {
            string str = "";
            str += BEGAIN_CHAR;
            str += HEAD_DUT_QUERY;
            str += " ";
            str += testTeam.ToString("D2");
            str += END_CHAR;
            return str;
        }
        static public bool ParseStartCmd(string data, ref int teamId, ref bool[] outFlag)
        {
            string[] flagList = data.Split(' ');
            if (flagList.GetLength(0) == 2 && flagList[1].Length == outFlag.Length)
            {
                int i = 0;
                teamId = Int32.Parse(flagList[0]);
                outFlag = new bool[flagList[1].Length];
                foreach (char str in flagList[1])
                {

                    if (str == '1')
                    {
                        outFlag[i] = true;
                    }
                    i++;
                }
                return true;
            }
            return false;
        }

        static public bool ParseCheckReadyCmd(string data, ref int teamId, ref bool[] groupWorkFlag)
        {
            string[] param = data.Split(' ');
            if (param.Length == 2)
            {
                if (!int.TryParse(param[0], out teamId))
                {
                    return false;
                }
                int i = 0;
                int groupId = 0;
                int dutId = 0;
                foreach (char str in param[1])
                {

                    if (str == '1')
                    {
                        if (DutsLogicalMap.ConventUIdToGroupDutId(i, ref groupId, ref dutId))
                        {
                            groupWorkFlag[groupId] = true;
                        }
                        else
                        {
                            return false;
                        }
                    }
                    i++;
                }
                return true;
            }

            return false;
        }

        static public bool ParseResultAckCmd(string data, ref int teamId)
        {
            int parseId = 0;
            if (int.TryParse(data, out parseId))
            {
                teamId = parseId;
                return true;
            }
            return false;
        }

        static public bool ParseSyncTemperatureAck(string data, ref int statusCode)
        {
            int parseId = 0;
            if (int.TryParse(data, out parseId))
            {
                statusCode = parseId;
                return true;
            }
            return false;
        }

        static public bool ParseDutsStatusAck(string data, ref int teamId, ref bool[] dutsWorkFlag)
        {
            int parseId = 0;
            int i = 0;
            string[] paramString = data.Split(' ');
            if (paramString.Length == 2)
            {
                if (!int.TryParse(paramString[0], out parseId))
                {
                    return false;
                }
                dutsWorkFlag = new bool[paramString[1].Length];
                foreach (char str in paramString[1])
                {
                    if (str == '1')
                    {
                        dutsWorkFlag[i] = true;
                    }
                    i++;
                }
            }
            return false;
        }

        static public string EncodeSystemStatusAlarm(string warnning, int serial)
        {
            string str = "";
            str += BEGAIN_CHAR;
            str += HEAD_ALARM_REQ;
            str += " ";
            str += serial.ToString();
            str += " ";
            str += warnning;
            str += END_CHAR;
            return str;
        }
        static public bool ParseAlarmAck(string data, ref UInt32 serial)
        {
            UInt32 parseSerial = 0;
            if (UInt32.TryParse(data, out parseSerial))
            {
                serial = parseSerial;
                return true;
            }
            return false;
        }
    }
}
