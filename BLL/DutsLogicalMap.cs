using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Hsg.BLL
{
    /// <summary>
    /// 逻辑位置为 UI显示或者分选机台指令中的顺序
    /// 物理位置 为 dut 在通讯板上 设计位置。
    /// </summary>
    public  class DutsLogicalMap
    {
        
        /// <summary>
        ///  从 物理位置到逻辑位置
        /// </summary>
        /// <param name="dutIndex">begin from 0</param>
        /// <param name="groupId"></param>
        /// <returns></returns>
        public static int ConventIdToUI(int dutIndex, int groupId)
        {
            int line = dutIndex / 4;
            int row = dutIndex % 4;
            return (line * 8) + row + groupId * 4;
        }
        /// <summary>
        /// 从逻辑到物理位置
        /// </summary>
        /// <param name="dutUid">0~23</param>
        /// <param name="groupId">0-1</param>
        /// <param name="dutIndex">0~11</param>
        /// <returns></returns>
        public static bool ConventUIdToGroupDutId(int dutUid, ref int groupId,ref int dutIndex)
        {
            groupId = dutUid % 8 / 4;
            dutIndex = dutUid /8 * 4 + dutUid%4;
            return true;
        }
        public static int ConventIdToBoard(int dutIndex, int dutOrder)
        {
            int line = 0;
            if (dutOrder == SysConfig.DUT_ORDER_RIGHT_TO_LEFT)
            {
                line = (byte)(SysConfig.PORT_NUM - 1 - dutIndex);
            }
            else
            {
                line = (byte)dutIndex;
            }
            return line;
        }
        
    }
}
