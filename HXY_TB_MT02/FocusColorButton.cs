using System;
using System.Collections.Generic;
using System.Drawing;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace Hsg.View
{
    public class FocusColorButton : Button
    {
        private Color _originalBackColor;

        public FocusColorButton()
        {
            // 初始化原始背景色（可以设置为按钮的默认背景色或其他颜色）
            
        }

        protected override void OnEnter(EventArgs e)
        {
            base.OnEnter(e);
            _originalBackColor = this.BackColor;
            // 当按钮获得焦点时，改变背景色为较淡的颜色
            this.BackColor = Color.FromArgb(_originalBackColor.A, Color.PaleGoldenrod); // 这里可以根据需要自定义淡色
            this.Invalidate(); // 通知控件重绘
        }

        protected override void OnLeave(EventArgs e)
        {
            base.OnLeave(e);
            // 当按钮失去焦点时，恢复原始背景色
            this.BackColor = _originalBackColor;
            this.Invalidate(); // 通知控件重绘
        }
    }
}
