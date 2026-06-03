using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Hsg.Common
{
    public class HsgLogger : IHsgLogger
    {
        private enum LogType
        {
            LOG_W,
            LOG_E,
            LOG_I,
            LOG_D
        }
        private string _moduleName;
        public HsgLogger(string moduleName = "")
        {
            if(moduleName?.Length>0)
            {
                _moduleName = "[" + moduleName + "]";
            } else
            {
                _moduleName = "";
            }
           
        }
        public void Debug(string msg)
        {
            PrintLog(LogType.LOG_D, _moduleName + " " + msg);
        }

        public void Error(string msg)
        {
            PrintLog(LogType.LOG_E, _moduleName + " " + msg);
        }

        public void Error(string msg, Exception ex)
        {
            PrintLog(LogType.LOG_E, _moduleName + " " + msg + "ex:" + ex.Message);
        }

        public void Info(string msg)
        {
            PrintLog(LogType.LOG_I, _moduleName + " " + msg);
        }

        public void Warning(string msg)
        {
            PrintLog(LogType.LOG_W, _moduleName + " " + msg);
        }
        private static void PrintLog(LogType type, string msg)
        {
            string logTag = "";
            switch (type)
            {
                case LogType.LOG_W:
                    logTag = "[W]";
                    break;
                case LogType.LOG_I:
                    logTag = "[I]";
                    break;
                case LogType.LOG_D:
                    logTag = "[D]";
                    break;
                case LogType.LOG_E:
                    logTag = "[E]";
                    break;
            }

            string log = DateTime.Now.ToString("[HH:mm:ss:fff]") + logTag + msg;
            Trace.WriteLine(log);
            // Console.WriteLine(log);
            //Trace.WriteLine(log);
            //if (SaveToFile)
            //{
            //    //TraceListener.Flush();
            //    Trace.Flush();
            //}
        }
    }
}
