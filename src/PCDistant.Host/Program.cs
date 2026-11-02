using System.Diagnostics;
using System.Drawing.Imaging;
using System.Net;
using System.Net.Sockets;
using System.Security.Cryptography;
using System.Text;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Logging;

namespace PCDistant.Host;

internal static class Program
{
    [STAThread]
    static void Main()
    {
        ApplicationConfiguration.Initialize();
        Application.Run(new HostWindow());
    }
}

public sealed class HostWindow : Form
{
    private readonly string token = Convert.ToHexString(RandomNumberGenerator.GetBytes(16));
    private readonly Button toggle = new() { Text = "Activer le partage", AutoSize = true };
    private readonly Label status = new() { Text = "Partage désactivé", AutoSize = true };
    private readonly Label activity = new() { Text = "Aucune demande reçue", AutoSize = true };
    private WebApplication? server;
    private bool closing;

    public HostWindow()
    {
        Text = "PCDistant — partage local";
        ClientSize = new Size(680, 410);
        MinimumSize = new Size(600, 400);
        var layout = new FlowLayoutPanel { Dock = DockStyle.Fill, FlowDirection = FlowDirection.TopDown,
            WrapContents = false, Padding = new Padding(24), AutoScroll = true };
        layout.Controls.Add(new Label { Text = "PCDistant", Font = new Font("Segoe UI", 22, FontStyle.Bold), AutoSize = true });
        layout.Controls.Add(new Label { Text = "Autorisez uniquement un appareil de confiance sur votre réseau privé.", AutoSize = true });
        var addresses = Dns.GetHostAddresses(Dns.GetHostName())
            .Where(a => a.AddressFamily == AddressFamily.InterNetwork && !IPAddress.IsLoopback(a))
            .Select(a => $"http://{a}:5080");
        layout.Controls.Add(new Label { Text = "Adresse du PC (Wi-Fi / Ethernet) :", AutoSize = true });
        layout.Controls.Add(new TextBox { Text = string.Join(Environment.NewLine, addresses), ReadOnly = true,
            Multiline = true, Width = 610, Height = 65 });
        layout.Controls.Add(new Label { Text = "Code d'accès (renouvelé à chaque lancement) :", AutoSize = true });
        layout.Controls.Add(new TextBox { Text = token, ReadOnly = true, Width = 500 });
        layout.Controls.Add(new Label { Text = "Partage : écran principal et applications avec une fenêtre visible.\nLes titres des fenêtres peuvent contenir des informations privées.", AutoSize = true });
        layout.Controls.Add(toggle);
        layout.Controls.Add(status);
        layout.Controls.Add(activity);
        Controls.Add(layout);
        toggle.Click += async (_, _) => await ToggleAsync();
        FormClosing += async (_, e) =>
        {
            if (closing || server is null) return;
            e.Cancel = true;
            closing = true;
            toggle.Enabled = false;
            await StopAsync();
            Close();
        };
    }

    private async Task ToggleAsync()
    {
        toggle.Enabled = false;
        try
        {
            if (server is not null) { await StopAsync(); return; }
            var builder = WebApplication.CreateSlimBuilder();
            builder.Logging.ClearProviders(); // Ne pas journaliser les secrets ou les données partagées.
            builder.WebHost.UseUrls("http://0.0.0.0:5080");
            var app = builder.Build();
            app.Use(async (context, next) =>
            {
                context.Response.Headers.CacheControl = "no-store";
                var supplied = context.Request.Headers.Authorization.ToString();
                var expected = "Bearer " + token;
                if (!CryptographicOperations.FixedTimeEquals(Encoding.UTF8.GetBytes(supplied), Encoding.UTF8.GetBytes(expected)))
                {
                    context.Response.StatusCode = 401;
                    return;
                }
                await next(context);
            });
            app.MapGet("/api/apps", () =>
            {
                RecordActivity("Liste des applications demandée");
                var apps = new List<AppInfo>();
                foreach (var process in Process.GetProcesses())
                {
                    using (process)
                    {
                        try
                        {
                            if (process.MainWindowHandle != IntPtr.Zero && !string.IsNullOrWhiteSpace(process.MainWindowTitle))
                                apps.Add(new(process.Id, process.ProcessName, process.MainWindowTitle));
                        }
                        catch (Exception ex) when (ex is System.ComponentModel.Win32Exception or InvalidOperationException or NotSupportedException) { }
                    }
                }
                return Results.Ok(apps.OrderBy(a => a.Name).ToArray());
            });
            app.MapGet("/api/screenshot", async () =>
            {
                try
                {
                    // La capture est exécutée sur le thread graphique de la session utilisateur.
                    var completion = new TaskCompletionSource<byte[]>(TaskCreationOptions.RunContinuationsAsynchronously);
                    BeginInvoke(new Action(() =>
                    {
                        try
                        {
                            var bounds = Screen.PrimaryScreen?.Bounds ?? throw new InvalidOperationException("Écran indisponible");
                            using var bitmap = new Bitmap(bounds.Width, bounds.Height);
                            using (var graphics = Graphics.FromImage(bitmap))
                                graphics.CopyFromScreen(bounds.Location, Point.Empty, bounds.Size);
                            using var stream = new MemoryStream();
                            bitmap.Save(stream, ImageFormat.Png);
                            completion.SetResult(stream.ToArray());
                            activity.Text = $"{DateTime.Now:T} — Capture demandée";
                        }
                        catch (Exception ex) { completion.SetException(ex); }
                    }));
                    return Results.File(await completion.Task, "image/png");
                }
                catch { return Results.Problem("Capture impossible. Vérifiez que la session Windows est ouverte et déverrouillée."); }
            });
            try { await app.StartAsync(); }
            catch { await app.DisposeAsync(); throw; }
            server = app;
            status.Text = "● Partage actif — restez sur un réseau privé de confiance";
            toggle.Text = "Arrêter le partage";
        }
        catch (Exception ex)
        {
            MessageBox.Show(this, "Impossible de démarrer le partage : " + ex.Message, "PCDistant", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
        finally { toggle.Enabled = true; }
    }

    private void RecordActivity(string message) => BeginInvoke(new Action(() => activity.Text = $"{DateTime.Now:T} — {message}"));

    private async Task StopAsync()
    {
        if (server is null) return;
        var current = server;
        server = null;
        using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(5));
        try { await current.StopAsync(timeout.Token); }
        finally
        {
            await current.DisposeAsync();
            status.Text = "Partage désactivé";
            toggle.Text = "Activer le partage";
        }
    }
}

public sealed record AppInfo(int Id, string Name, string Title);
