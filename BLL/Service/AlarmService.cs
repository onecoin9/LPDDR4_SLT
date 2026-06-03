using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Hsg.BLL.Service
{
    public delegate void ISendAlarm(int teamId, string msg);
    public enum AlarmType
    {
        None,// 无
        TBNet,//通讯板网络不通
        TCNet// 温控通讯异常
    }
    public class AlarmService
    {
        public static AlarmService instance = new AlarmService();
        private static ISendAlarm _sendFunction;
        private AlarmService()
        {
        }
        public static string AlarmTypeToString(AlarmType type)
        {
            switch (type)
            {
                case AlarmType.None:
                    return "";
                case AlarmType.TBNet:
                    return "通讯板通讯异常";
                case AlarmType.TCNet:
                    return "温控板异常";
            }
            return "";
        }
        public void BindSendFunction(ISendAlarm func)
        {
            _sendFunction = func;
        }
        public void SendAlarm(int teamId, string msg)
        {
            if (_sendFunction != null)
            {
                 _sendFunction.Invoke(teamId, msg);
            }
        }
    }
}
