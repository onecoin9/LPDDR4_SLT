using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Hsg.Common
{
    public enum TempState : byte
    {
        TmpNormal,// 常温
        TmpHight,// 高温
        TmpLow,// 低温
        TmpMixture,//高温常温组合
        TmpMax,
    }
    public class WorkStage
    {
        public const int ST_FT = 0;// 
        public const int ST_FRT = 1;
        public const int ST_PRT = 2;
        public const int ST_MFT = 3;
        public const int ST_PRT2 = 4;
        public const int ST_PRT3 = 5;
        static public bool GetStageInfo(int stageId, ref string stageName, ref string stageDescript)
        {
            switch (stageId)
            {
                case ST_FT:
                    stageDescript = "首测(单站)";
                    stageName = "FT";
                    break;
                case ST_FRT:
                    stageDescript = "终测";
                    stageName = "FRT";
                    break;
                case ST_PRT:
                    stageDescript = "复测-1";
                    stageName = "PRT";
                    break;
                case ST_MFT:
                    stageDescript = "首测(多站)";
                    stageName = "MFT";
                    break;
                case ST_PRT2:
                    stageDescript = "复测-2";
                    stageName = "PRT2";
                    break;
                case ST_PRT3:
                    stageDescript = "复测-3";
                    stageName = "PRT3";
                    break;
                default:
                    return false;

            }
            return true;
        }
    }
}
