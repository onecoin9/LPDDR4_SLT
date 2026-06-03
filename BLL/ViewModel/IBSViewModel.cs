using Hsg.Common;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Hsg.BLL.ViewModel
{
    public interface IBSViewModel
    {
        /// <summary>
        /// 测试时间
        /// </summary>
        string WorkTime { get; set; }


        /// <summary>
        /// Handle server connect state
        /// </summary>
        ConnState HandleServerConnState { get; set; }

        //bool IsDebugMode {  get; set; }
        /// <summary>
        /// 给model 使用
        /// </summary>
        bool ServiceStart { get; set; }
        /// <summary>
        /// 服务是否就绪
        /// </summary>
        bool ServiceReady { get; set; }
        /// <summary>
        /// 给model 使用
        /// </summary>
        int OnlineBoard { get; set; }

       /// <summary>
       /// 策略文件名称
       /// </summary>
        string PolicyName { get; set; }
        /// <summary>
        /// 测试中的数目
        /// </summary>
        int TestingTeamNum { get; set; }
        /// <summary>
        /// 测试通过的数目
        /// </summary>
        int PassDutNum { get; set; }
        /// <summary>
        /// 测试总数
        /// </summary>
        int TestDutNum { get; set; }
        /// <summary>
        /// 是否可用
        /// </summary>
        bool ViewEnable {  get; set; }
    }
}
