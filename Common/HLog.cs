using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.IO;
using System.Diagnostics;

namespace Hsg.Common
{
    /// <summary>
    /// 用于打印调试log
    /// </summary>
    public class Hlog
    {
        public static bool SaveToFile = false;
        public static bool LogEnable = false;
        private const bool DEBUG_CONSOLE = true;
        private const string DEFAULT_MODE = "HG";
        private static  int _logStartDay = DateTime.Now.Day;
        private static readonly Object _writeLock = new object();
        private static LogType LogLevel = LogType.LOG_D;
      //  private static string LogFileName = DateTime.Now.ToString("yyyy_MM_dd HH.mm.ss") + "TestTool.log";
        // 构造完整的日志保存路径
        private static string Log_SAVE_PATH = AppDomain.CurrentDomain.BaseDirectory + "Log\\" ;
        private enum LogType
        {
            LOG_E,
            LOG_W,
            LOG_I,
            LOG_D
        }
        private static string GetLoagFieName()
        {
            return DateTime.Now.ToString("yyyy_MM_dd HH.mm.ss") + "TestTool.log";
        }
        public static void SetLogLevel(int level)
        {
            if(level>=0 && level<= (int)LogType.LOG_D)
            {
                LogLevel = LogType.LOG_E + level;
            }
        }
        private static System.Diagnostics.TextWriterTraceListener TraceListener;
        public static void W(string mod, string log)
        {
            string msg = "[" + mod + "]" + log;
            PrintLog(LogType.LOG_W, msg);
        }
        public static void W(string log)
        {
            string msg = "[" + DEFAULT_MODE + "]" + log;
            PrintLog(LogType.LOG_W, msg);
        }
        public static void E(string mod, string log)
        {
            string msg = "[" + mod + "]" + log;
            PrintLog(LogType.LOG_E, msg);
        }
        public static void E(string log)
        {
            string msg = "[" + DEFAULT_MODE + "]" + log;
            PrintLog(LogType.LOG_E, msg);
        }
        public static void I(string mod, string log)
        {
            string msg = "[" + mod + "]" + log;
            PrintLog(LogType.LOG_I, msg);
        }
        public static void I(string log)
        {
            string msg = "[" + DEFAULT_MODE + "]" + log;
            PrintLog(LogType.LOG_I, msg);
        }
        public static void D(string mod, string log)
        {
            string msg = "[" + mod + "]" + log;
            PrintLog(LogType.LOG_D, msg);
        }
        public static void D(string log)
        {
            string msg = "[" + DEFAULT_MODE + "]" + log;
            PrintLog(LogType.LOG_D, msg);
        }
        private static void PrintLog(LogType type, string msg)
        {
            string logTag = "";
            if(type > LogLevel)
            {
                return;
            }
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
#if false
            if (DEBUG_CONSOLE)
            {
                string log = logTag + msg;

                Console.WriteLine(log);
            }
#else
            {
                string log = DateTime.Now.ToString("[HH:mm:ss:fff]") + logTag + msg ;
                //Debug.WriteLine(log);
                if(LogEnable)
                {
                    lock(_writeLock)
                    {
                        try
                        {
                            Trace.WriteLine(log);
                        }
                        catch
                        {
                            Console.WriteLine("write error");
                        }
                        
                        if (SaveToFile)
                        {
                            if (_logStartDay != DateTime.Now.Day)
                            {
                                _logStartDay = DateTime.Now.Day;
                                //Trace.Flush();
                                Trace.Listeners.Remove(TraceListener);
                                TraceListener.Close();
                                TraceListener = new System.Diagnostics.TextWriterTraceListener(Log_SAVE_PATH + GetLoagFieName());
                                Trace.Listeners.Add(TraceListener);
                            }
                            
                            //TraceListener.Flush();
                        }
                    }
                }
            }
#endif        
        }
        public static void UserDebugSaveFile()
        {
            if (!Directory.Exists(Log_SAVE_PATH))
            {
                Directory.CreateDirectory(Log_SAVE_PATH);
            }
            TraceListener  = new System.Diagnostics.TextWriterTraceListener(Log_SAVE_PATH + GetLoagFieName());
            Trace.Listeners.Add(TraceListener);
            Trace.AutoFlush = true;
            //System.Diagnostics.Debug.WriteLine(System.DateTime.Now.ToString());
            SaveToFile = true;
            LogEnable = true;
        }
    }
}
