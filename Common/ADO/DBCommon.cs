using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Hsg.Common.ADO
{
    
    public class DBData
    {
        public DBData(string name, int size)
        {
            this.name = name;
            this.size = size;
        }
        public string name;
        public int size;
    }

    public class DBTableColumn
    {
        public static DBData OrderNo = new DBData("orderNo", 16);
        public static DBData MaterialNo = new DBData("materialNo", 16);
        public static DBData WorkOrderNo = new DBData("workOrderNo", 16);
        public static DBData CfgName = new DBData("cfgName", 128);
        public static string TempStateToString(byte state)
        {
            switch(state)
            {
                case (byte)TempState.TmpHight:
                    return "高温";
                case (byte)TempState.TmpLow:
                    return "低温";
                case (byte)TempState.TmpNormal:
                    return "室温";
                case (byte)TempState.TmpMixture:
                    return "高/室温";
                default:
                    return "";
            }
        }
    }


    public class AbnormalRecord
    {
        public int id;
        public short code;
        public int count;
        public string extra;
    }
}
