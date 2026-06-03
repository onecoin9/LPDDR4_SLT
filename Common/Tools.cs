using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Net.NetworkInformation;
using System.Net;
using System.Diagnostics;
using System.Threading;
using System.Runtime.InteropServices;
using System.IO;

namespace Hsg.Common
{
    public class Tools
    {
        [DllImport("user32.dll")]
        private static extern IntPtr FindWindow(string lpClassName, string lpWindowName);
        [DllImport("user32.dll", CharSet = CharSet.Auto)]
        public static extern int SendMessage(IntPtr hWnd, int msg, int wParam, int lParam);
        [DllImport("user32.dll", CharSet = CharSet.Auto)]
        public static extern int PostMessage(IntPtr hWnd, int msg, int wParam, int lParam);
        public static bool PingIp(string ip, int mseconde)
        {
            Ping p = new Ping();
            byte[] sendData = new byte[2] { 0x88, 0x99 };
            PingOptions opts = new PingOptions();
            opts.DontFragment = true;
#if _DEBUG_ON
            return true;
#endif
            try
            {
                PingReply reply = p.Send(IPAddress.Parse(ip), mseconde, sendData);
                if (reply != null && reply.Status == IPStatus.Success)
                {
                    return true;
                }
            }
            catch
            {

            }
            return false;
        }

        public static string HexToString(byte[] data)
        {
            var hexBuilder = new StringBuilder(data.Length * 4);
            foreach (var v in data)
            {
                hexBuilder.AppendFormat("{0:x2} ", v);
            }
            string hexStr = String.Format(@"{0}", hexBuilder);
            return hexStr;
        }

        public static string TimeSpanToString(TimeSpan span)
        {
            int hour = span.Days * 24 + span.Hours;
            int minute = span.Minutes;
            int second = span.Seconds;
            string timeString = string.Format(@"{0}:{1}:{2}", hour.ToString("D2"),
                minute.ToString("D2"), second.ToString("D2"));
            return timeString;
        }

        public static async Task<bool> SendMessageToLauchWindow(string processName, int message, UInt32 wparam, UInt32 lparam, bool startRetry = true)
        {
            //IntPtr windowHandle = FindWindow(null, processName);
            IntPtr windowHandle = IntPtr.Zero;
            Process process = new Process();
            process.StartInfo.Arguments = "show";
            process.StartInfo.FileName = processName;
            try
            {
                if (processName.EndsWith(".exe"))
                {
                    windowHandle = FindWindow(null, processName.Substring(0, processName.Length - 4));
                }
                else
                {
                    windowHandle = FindWindow(null, processName);
                }

                if (windowHandle == IntPtr.Zero && startRetry)
                {
                    if (process.Start())
                    {
                        // Thread.Sleep(500);
                        await Task.Delay(800);
                        if (processName.EndsWith(".exe"))
                        {
                            windowHandle = FindWindow(null, processName.Substring(0, processName.Length - 4));
                        }
                        else
                        {
                            windowHandle = FindWindow(null, processName);
                        }
                    }
                }
            }
            catch
            {
                return false;
            }

            if (windowHandle != IntPtr.Zero)
            {
                SendMessage(windowHandle, message, (int)wparam, (int)lparam);
                return true;
            }
            return false;
        }
        public static bool PostMessageToLauchWindow(string processName, int message, UInt32 wparam, UInt32 lparam,bool startRetry = true)
        {
            //IntPtr windowHandle = FindWindow(null, processName);
            IntPtr windowHandle = IntPtr.Zero;
            Process process = new Process();
            process.StartInfo.Arguments = "show";
            process.StartInfo.FileName = processName;
            try
            {
                if (processName.EndsWith(".exe"))
                {
                    windowHandle = FindWindow(null, processName.Substring(0, processName.Length - 4));
                }
                else
                {
                    windowHandle = FindWindow(null, processName);
                }

                if (windowHandle == IntPtr.Zero && startRetry)
                {
                    if (process.Start())
                    {
                        //Thread.Sleep(200);
                        Task.Delay(200).Wait();
                        if (processName.EndsWith(".exe"))
                        {
                            windowHandle = FindWindow(null, processName.Substring(0, processName.Length - 4));
                        }
                        else
                        {
                            windowHandle = FindWindow(null, processName);
                        }
                    }
                }
            }
            catch
            {
                return false;
            }

            if (windowHandle != IntPtr.Zero)
            {
                PostMessage(windowHandle, message, (int)wparam, (int)lparam);
                return true;
            }
            return false;
        }

        public static UInt32 GetTimestampToSecond()
        {
            TimeSpan span = DateTime.Now.ToUniversalTime() - new DateTime(1970, 1, 1, 0, 0, 0); ;
            return (uint)span.TotalSeconds;
        }
        public static string GetRelativePath(string baseDir, string fullFilePath)
        {
            // 确保两个路径使用相同的目录分隔符
            baseDir = Path.GetFullPath(baseDir);
            fullFilePath = Path.GetFullPath(fullFilePath);

            // 获取路径的目录部分
            string baseDirPath = baseDir;
            string fullFilePathDir = Path.GetDirectoryName(fullFilePath);

            // 获取每个目录的各个部分
            string[] baseDirParts = baseDirPath.Split(Path.DirectorySeparatorChar);
            string[] fullFilePathParts = fullFilePathDir.Split(Path.DirectorySeparatorChar);

            // 找到公共前缀的长度
            int commonPrefixLength = 0;
            while (commonPrefixLength < baseDirParts.Length && commonPrefixLength < fullFilePathParts.Length
                   && baseDirParts[commonPrefixLength] == fullFilePathParts[commonPrefixLength])
            {
                commonPrefixLength++;
            }

            // 计算相对路径
            string relativePath = string.Empty;
            for (int i = commonPrefixLength; i < baseDirParts.Length; i++)
            {
                relativePath += ".." + Path.DirectorySeparatorChar;
            }

            for (int i = commonPrefixLength; i < fullFilePathParts.Length; i++)
            {
                relativePath += fullFilePathParts[i] + Path.DirectorySeparatorChar;
            }

            // 添加文件名
            relativePath += Path.GetFileName(fullFilePath);

            return relativePath;
        }

    }
}
