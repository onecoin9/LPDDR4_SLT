using Hsg.Common;
using Hsg.Common.ADO;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Hsg.BLL
{
    public enum StateRecordIndex
    {
        TempCtr,
        //CommunicateBoard01,
        //CommunicateBoard02,
        DutIndexBegin,
        DutIndexEnd = DutIndexBegin + SysConfig.TEAM_GROUP_NUM * SysConfig.PORT_NUM,
        TotalCount = DutIndexEnd
    }
    public enum AbnormalRecordIndex
    {
        TempCtr,
        CommunicateBoard01,
        CommunicateBoard02,
        DutIndexBegin,
        DutIndexEnd = DutIndexBegin + SysConfig.TEAM_GROUP_NUM * SysConfig.PORT_NUM,
        TotalCount = DutIndexEnd
    }
    internal class StateRecord
    {
        public ObservableArray<short> lastStateCode;
        public short[] continueCount;
    }


    public class TeamStateManager
    {
        private DBHandler _dbHandler;
        private List<StateRecord> _boxDutStates;// 记录最近的测试状况
        private static TeamStateManager _instance;
        private const string Mod = "DutsStateManager";
        private static readonly object _classLock = new object();
        private TeamStateManager()
        {
            _boxDutStates = new List<StateRecord>();
            _dbHandler = DBHandler.Instance;
            for (int i = 0; i < SysConfig.DEV_NUM; i++)
            {
                short[] stateValue = new short[(int)StateRecordIndex.TotalCount];
                short[] continueCount = new short[(int)StateRecordIndex.TotalCount];
                _dbHandler.QueryDutsLastStateCode(i + 1, ref stateValue, ref continueCount);
                ObservableArray<short> item = new ObservableArray<short>(stateValue, i);
                item.OnArrayChange += onMemberStateChange;
                StateRecord record = new StateRecord();
                record.continueCount = continueCount;
                record.lastStateCode = item;
                _boxDutStates.Add(record);
            }
        }
        private void onMemberStateChange(int dutIndex, object param)
        {
            int boxId = Int32.Parse(param.ToString());
            if (!_dbHandler.UpdateDutLastStateCode(boxId + 1, dutIndex, _boxDutStates[boxId].lastStateCode[dutIndex]))
            {
                var boxNo = boxId + 1;
                var dutNo = dutIndex;
                short value = _boxDutStates[boxId].lastStateCode[dutIndex];
                Hlog.E(Mod, $"save state {boxNo} {dutNo} {value} failed.");
            }
        }
        public static TeamStateManager GetInstance()
        {
            if (_instance == null)
            {
                lock (_classLock)
                {
                    if (_instance == null)
                    {
                        _instance = new TeamStateManager();
                    }
                }
            }
            return _instance;
        }
        public bool LoadTeamMemberLastStateCode(int teamIndex, ref ushort[] stateCode, ref ushort []continueCount)
        {
            if (teamIndex < 0 || teamIndex >= _boxDutStates.Count)
            {
                return false;
            }
            stateCode = new ushort[(int)StateRecordIndex.TotalCount];
            continueCount = new ushort[(int)StateRecordIndex.TotalCount];
            for (int i = 0; i < stateCode.Length; i++)
            {
                stateCode[i] = (ushort)_boxDutStates[teamIndex].lastStateCode[i];
                continueCount[i] = (ushort)_boxDutStates[teamIndex].continueCount[i];
            }
            return true;
        }


        /// <summary>
        /// 获取环境异常记录
        /// </summary>
        /// <param name="teamIndex"></param>
        /// <param name="stateCode"></param>
        /// <param name="continueCount"></param>
        /// <returns></returns>
        public bool LoadTeamMemberEvtAbnormalRecord(int teamIndex, ref List<AbnormalRecord> readRecord)
        {
            if (teamIndex < 0 || teamIndex >= _boxDutStates.Count)
            {
                return false;
            }
            _dbHandler.QueryComponentAbnormalRecord(teamIndex + 1, ref readRecord);
 
            return true;
        }

        public bool ClearTeamMemberEvtAbnormalRecord(int teamIndex)
        {
            if (teamIndex < 0 || teamIndex >= _boxDutStates.Count)
            {
                return false;
            }

            if (!_dbHandler.DeleteComponentAbnormalRecord(teamIndex + 1))
            {
                var boxNo = teamIndex + 1;
                Hlog.E(Mod, $"delete abnormal {boxNo}  failed.");
            }
            return true;
        }

        public bool ClearTeamMemberEvtAbnormalRecord(int teamIndex, int componmentId, short code)
        {
            if (teamIndex < 0 
                || teamIndex >= _boxDutStates.Count 
                || componmentId <(int)(AbnormalRecordIndex.TempCtr)
                || componmentId >= (int)AbnormalRecordIndex.TotalCount)
            {
                return false;
            }

            if (!_dbHandler.DeleteComponentAbnormalRecord(teamIndex + 1, componmentId, code))
            {
                var boxNo = teamIndex + 1;
                Hlog.E(Mod, $"delete abnormal {boxNo} {componmentId} failed.");
            }
            return true;
        }

        public void UpdateDutsStateCode(int boxId, ushort[] stateCode,string []extraInfo=null)
        {
            ushort abnormalCode = 0;
            if (boxId >= 0 && boxId < _boxDutStates.Count)
            {
                for (int i = 0; i < _boxDutStates[boxId].lastStateCode.Length - (int)StateRecordIndex.DutIndexBegin && i < stateCode.Length; i++)
                {
                    if (!DutMaster.CheckStateCodeAbnormal(stateCode[i], ref abnormalCode))
                    {
                        continue;
                    }
                    if(DutMaster.FoundEnvoriementAbnormalCode(abnormalCode)) //记录Dut环境状态异常
                    {
                        int componmentId = i + (int)AbnormalRecordIndex.DutIndexBegin;
                        if(!_dbHandler.AddComponentNewAbnormalRecord(boxId + 1, componmentId, (short)stateCode[i], extraInfo[i]))
                        {
                            int boxNo = boxId + 1;
                            Hlog.E(Mod, $"add abnormal {boxNo} {componmentId} {stateCode[i]} failed.");
                        }
                    }
                    if (DutMaster.FoundMainBoradState(abnormalCode))// 用来区分主板的状态
                    {
                        continue;
                    }
                    int dutIndex = i + (int)StateRecordIndex.DutIndexBegin;
                    if(_boxDutStates[boxId].lastStateCode[dutIndex] != (short)stateCode[i])
                    {
                        // 这里不需要保存，因为lastStateCode 关联的set 方法会保存变动
                        _boxDutStates[boxId].lastStateCode[dutIndex] = (short)stateCode[i];
                        _boxDutStates[boxId].continueCount[dutIndex] = 1;
                    }
                    else if(_boxDutStates[boxId].lastStateCode[dutIndex] != StateCode.SCODE_OK)
                    {
                        _boxDutStates[boxId].continueCount[dutIndex]++;
                        _dbHandler.UpdateDutLastStateCodeCount(boxId + 1, dutIndex, (short)stateCode[i], _boxDutStates[boxId].continueCount[dutIndex]);
                    }
                }
            }
        }

        public void UpdateTempCtrStateCode(int boxId, ushort stateCode,string extraInfor=null)
        {
            if(stateCode != StateCode.SCODE_OK) // 只记录异常
            {
                int componmentId = (int)AbnormalRecordIndex.TempCtr;
                if (!_dbHandler.AddComponentNewAbnormalRecord(boxId + 1, componmentId, (short)stateCode, extraInfor))
                {
                    int boxNo = boxId + 1;
                    Hlog.E(Mod, $"add abnormal {boxNo} {componmentId} {stateCode} failed.");
                }
            }
            
            // 记录最近的一次状态
            if (_boxDutStates[boxId].lastStateCode[(int)StateRecordIndex.TempCtr] != (short)stateCode)
            {
                // 这里不需要保存，因为lastStateCode 关联的set 方法会保存变动
                _boxDutStates[boxId].lastStateCode[(int)StateRecordIndex.TempCtr] = (short)stateCode;
                _boxDutStates[boxId].continueCount[(int)StateRecordIndex.TempCtr] = 1;
            } else if(stateCode != StateCode.SCODE_OK)
            {
                _boxDutStates[boxId].continueCount[(int)StateRecordIndex.TempCtr]++;
                _dbHandler.UpdateDutLastStateCodeCount(boxId + 1, (int)StateRecordIndex.TempCtr, (short)stateCode, _boxDutStates[boxId].continueCount[(int)StateRecordIndex.TempCtr]);
            }
        }

        //上报通讯板通讯故障
        public void RecordCommunicateTBAbnormal(int boxId, int boardId)
        {
            if (boardId >=0 && boardId<=1)
            {
                int componmentId = boardId + (int)AbnormalRecordIndex.CommunicateBoard01;

                if (!_dbHandler.AddComponentNewAbnormalRecord(boxId + 1, componmentId, (short)StateCode.SCODE_TB_COMMUNICATE_ERROR, ""))
                {
                    int boxNo = boxId + 1;
                    Hlog.E(Mod, $"add abnormal {boxNo} {componmentId} {StateCode.SCODE_TB_COMMUNICATE_ERROR} failed.");
                }
            }
        }
        //public void UpdateCommunicateBoardStateCode(int boxId, int groupId, ushort stateCode)
        //{
        //    if(groupId == 0)
        //    {
        //        _boxDutStates[boxId][(int)StateRecordIndex.CommunicateBoard01] = (short)stateCode;
        //    }
        //    else
        //    {
        //        _boxDutStates[boxId][(int)StateRecordIndex.CommunicateBoard02] = (short)stateCode;
        //    }

        //}
    }
}
