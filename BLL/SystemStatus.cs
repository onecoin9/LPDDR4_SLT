using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Hsg.BLL
{
    internal class SystemStatus
    {
        // private static bool _debugMode = false;
        public static bool DebugMode
        {
            get { return SysConfig.WorkMode == Common.WorkMode.Debug; }
            // set { _debugMode = value; }
        }
        public static bool DebugBoardTest
        {
            get { return SysConfig.WorkMode == Common.WorkMode.Debug && SysConfig.GetInstance().DebugBoardTest.Value == "1"; }
        }
    }
}
