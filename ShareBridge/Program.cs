using System;
using System.Windows.Forms;
using Windows.ApplicationModel.DataTransfer;
using Windows.Storage;
using WinRT.Interop;

class Program
{
    [STAThread]
    static void Main(string[] args)
    {
        if (args.Length < 1)
            return;

        string filePath = args[0];

        Application.EnableVisualStyles();

        var form = new Form();
        form.Width = 0;
        form.Height = 0;
        form.ShowInTaskbar = false;
        form.Opacity = 0;

        form.Load += async (s, e) =>
        {
            try
            {
                var hwnd = form.Handle;

                var dtm = DataTransferManagerInterop.GetForWindow(hwnd);

                dtm.DataRequested += async (sender, ev) =>
                {
                    var request = ev.Request;
                    request.Data.Properties.Title = "tFaha Share";

                    var file = await StorageFile.GetFileFromPathAsync(filePath);
                    request.Data.SetStorageItems(new[] { file });
                };

                DataTransferManagerInterop.ShowShareUIForWindow(hwnd);
            }
            catch (Exception ex)
            {
                MessageBox.Show(ex.ToString());
                System.IO.File.WriteAllText("error_log.txt", ex.ToString());
            }
        };

        Application.Run(form);
    }
}