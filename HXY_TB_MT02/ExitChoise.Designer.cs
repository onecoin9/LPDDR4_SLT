namespace Hsg.View
{
    partial class ExitChoise
    {
        /// <summary>
        /// Required designer variable.
        /// </summary>
        private System.ComponentModel.IContainer components = null;

        /// <summary>
        /// Clean up any resources being used.
        /// </summary>
        /// <param name="disposing">true if managed resources should be disposed; otherwise, false.</param>
        protected override void Dispose(bool disposing)
        {
            if (disposing && (components != null))
            {
                components.Dispose();
            }
            base.Dispose(disposing);
        }

        #region Windows Form Designer generated code

        /// <summary>
        /// Required method for Designer support - do not modify
        /// the contents of this method with the code editor.
        /// </summary>
        private void InitializeComponent()
        {
            System.ComponentModel.ComponentResourceManager resources = new System.ComponentModel.ComponentResourceManager(typeof(ExitChoise));
            this.m_btn_close_workOrder = new Hsg.View.FocusColorButton();
            this.label1 = new System.Windows.Forms.Label();
            this.m_btn_quit = new Hsg.View.FocusColorButton();
            this.m_btn_back = new Hsg.View.FocusColorButton();
            this.panel1 = new System.Windows.Forms.Panel();
            this.panel1.SuspendLayout();
            this.SuspendLayout();
            // 
            // m_btn_close_workOrder
            // 
            this.m_btn_close_workOrder.BackColor = System.Drawing.Color.LightCoral;
            this.m_btn_close_workOrder.Font = new System.Drawing.Font("新宋体", 14.25F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.m_btn_close_workOrder.Location = new System.Drawing.Point(8, 91);
            this.m_btn_close_workOrder.Margin = new System.Windows.Forms.Padding(5);
            this.m_btn_close_workOrder.Name = "m_btn_close_workOrder";
            this.m_btn_close_workOrder.Size = new System.Drawing.Size(107, 42);
            this.m_btn_close_workOrder.TabIndex = 0;
            this.m_btn_close_workOrder.Text = "关闭工单";
            this.m_btn_close_workOrder.UseVisualStyleBackColor = false;
            this.m_btn_close_workOrder.Click += new System.EventHandler(this.m_btn_close_workOrder_Click);
            // 
            // label1
            // 
            this.label1.AutoSize = true;
            this.label1.BackColor = System.Drawing.Color.Transparent;
            this.label1.Font = new System.Drawing.Font("新宋体", 14.25F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.label1.ForeColor = System.Drawing.Color.Yellow;
            this.label1.Location = new System.Drawing.Point(354, 249);
            this.label1.Name = "label1";
            this.label1.Size = new System.Drawing.Size(0, 29);
            this.label1.TabIndex = 1;
            // 
            // m_btn_quit
            // 
            this.m_btn_quit.BackColor = System.Drawing.Color.DeepSkyBlue;
            this.m_btn_quit.Font = new System.Drawing.Font("新宋体", 14.25F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.m_btn_quit.Location = new System.Drawing.Point(7, 33);
            this.m_btn_quit.Margin = new System.Windows.Forms.Padding(5);
            this.m_btn_quit.Name = "m_btn_quit";
            this.m_btn_quit.Size = new System.Drawing.Size(107, 42);
            this.m_btn_quit.TabIndex = 0;
            this.m_btn_quit.Text = "结束测试";
            this.m_btn_quit.UseVisualStyleBackColor = false;
            this.m_btn_quit.Click += new System.EventHandler(this.m_btn_quit_Click);
            // 
            // m_btn_back
            // 
            this.m_btn_back.BackColor = System.Drawing.Color.DeepSkyBlue;
            this.m_btn_back.Location = new System.Drawing.Point(8, 149);
            this.m_btn_back.Margin = new System.Windows.Forms.Padding(5);
            this.m_btn_back.Name = "m_btn_back";
            this.m_btn_back.Size = new System.Drawing.Size(107, 42);
            this.m_btn_back.TabIndex = 0;
            this.m_btn_back.Text = "返回测试";
            this.m_btn_back.UseVisualStyleBackColor = false;
            this.m_btn_back.Click += new System.EventHandler(this.m_btn_back_Click);
            // 
            // panel1
            // 
            this.panel1.BackColor = System.Drawing.SystemColors.ActiveCaptionText;
            this.panel1.Controls.Add(this.m_btn_quit);
            this.panel1.Controls.Add(this.m_btn_back);
            this.panel1.Controls.Add(this.m_btn_close_workOrder);
            this.panel1.Dock = System.Windows.Forms.DockStyle.Left;
            this.panel1.Location = new System.Drawing.Point(0, 0);
            this.panel1.Name = "panel1";
            this.panel1.Size = new System.Drawing.Size(125, 220);
            this.panel1.TabIndex = 3;
            // 
            // ExitChoise
            // 
            this.AutoScaleDimensions = new System.Drawing.SizeF(15F, 29F);
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.AutoValidate = System.Windows.Forms.AutoValidate.Disable;
            this.BackgroundImage = ((System.Drawing.Image)(resources.GetObject("$this.BackgroundImage")));
            this.BackgroundImageLayout = System.Windows.Forms.ImageLayout.Zoom;
            this.ClientSize = new System.Drawing.Size(460, 220);
            this.ControlBox = false;
            this.Controls.Add(this.panel1);
            this.Controls.Add(this.label1);
            this.DoubleBuffered = true;
            this.Font = new System.Drawing.Font("新宋体", 14.25F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.FormBorderStyle = System.Windows.Forms.FormBorderStyle.FixedDialog;
            this.Icon = ((System.Drawing.Icon)(resources.GetObject("$this.Icon")));
            this.Margin = new System.Windows.Forms.Padding(5);
            this.MaximizeBox = false;
            this.MinimizeBox = false;
            this.Name = "ExitChoise";
            this.ShowInTaskbar = false;
            this.SizeGripStyle = System.Windows.Forms.SizeGripStyle.Hide;
            this.StartPosition = System.Windows.Forms.FormStartPosition.CenterScreen;
            this.panel1.ResumeLayout(false);
            this.ResumeLayout(false);
            this.PerformLayout();

        }

        #endregion

        private FocusColorButton m_btn_close_workOrder;
        private System.Windows.Forms.Label label1;
        private FocusColorButton m_btn_quit;
        private FocusColorButton m_btn_back;
        private System.Windows.Forms.Panel panel1;
    }
}