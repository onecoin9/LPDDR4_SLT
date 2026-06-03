using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Drawing;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace Hsg.View
{

    public partial class ProgressWindow : Form
    {
        public String Title
        {
            get { return Text; }
            set { Text = value; }
        }

        private CircularProgressBar.CircularProgressBar circularProgressBar1;
        private int angle;
        private Action _ProcessEventPtr;
        public ProgressWindow(Action processEventPtr, string title)
        {
            _ProcessEventPtr = processEventPtr;

            circularProgressBar1 = new CircularProgressBar.CircularProgressBar();
            circularProgressBar1.Value = 20;
            // circularProgressBar1.OuterColor = System.Drawing.Color.White;
            //  circularProgressBar1.InnerColor = Color.Blue;
            circularProgressBar1.Style = ProgressBarStyle.Blocks;
            circularProgressBar1.Font = new Font(FontFamily.GenericSerif, 15);
            circularProgressBar1.Margin = new Padding(0);
            circularProgressBar1.ProgressColor = System.Drawing.Color.Gold;
            circularProgressBar1.ProgressWidth = 10;
            circularProgressBar1.Dock = DockStyle.Fill;
            circularProgressBar1.Margin = new Padding(30);
            //circularProgressBar1.Text = "等待完成";
            circularProgressBar1.SuperscriptText = "等待完成";
            circularProgressBar1.SubscriptColor = Color.Red;
            //circularProgressBar1.AnimationSpeed = 100;
            // circularProgressBar1.Size = m_pal_progress.Size;
            //circularProgressBar1.Font.si = 30;
            circularProgressBar1.StartAngle = angle;
            InitializeComponent();
            Title = title;
            m_pal_progress.Controls.Add(circularProgressBar1);

        }

        private void ProgressWindow_Load(object sender, EventArgs e)
        {
            // circularProgressBar1.Show();
            timer1.Interval = 5; // 每 1 毫秒更新一次角度  
            timer1.Tick += timer1_Tick;
            timer1.Start();
            Text = Title;
            Task.Run( () => {
                Task.Delay(1000).Wait();
                _ProcessEventPtr?.Invoke();
                Task.Delay(1000).Wait();
                this.Invoke((MethodInvoker)(() => CloseWindow()));
            });
        }

        private void CloseWindow()
        {
            timer1.Stop();
            Close();
        }

        private void timer1_Tick(object sender, EventArgs e)
        {
            angle += 2; // 每次增加 2 度  
            if (angle >= 360)
                angle = 0; // 当角度达到 360 度时重置为 0 度  
                           //  circularProgressBar1.Value = (int)((double)angle * 100 / 360);
            circularProgressBar1.StartAngle = angle; // 设置进度条的角度  
        }

        private void ProgressWindow_Shown(object sender, EventArgs e)
        {
            
        }
    }
}
