using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;

namespace PCDistant.Client;

public sealed class MainPage : ContentPage
{
    private readonly Entry address = new() { Placeholder = "http://192.168.1.10:5080", Keyboard = Keyboard.Url };
    private readonly Entry code = new() { Placeholder = "Code affiché sur le PC", IsPassword = true, IsTextPredictionEnabled = false };
    private readonly Label status = new() { Text = "Prêt à se connecter" };
    private readonly Image screenshot = new() { Aspect = Aspect.AspectFit, HeightRequest = 280 };
    private readonly VerticalStackLayout apps = new() { Spacing = 8 };
    private readonly Button captureButton = new() { Text = "Demander une capture" };
    private readonly Button appsButton = new() { Text = "Lister les applications" };
    private readonly HttpClient http = new(new HttpClientHandler { AllowAutoRedirect = false })
    { Timeout = TimeSpan.FromSeconds(20), MaxResponseContentBufferSize = 32 * 1024 * 1024 };

    public MainPage()
    {
        Title = "PCDistant";
        BackgroundColor = Color.FromArgb("#F3F6FA");
        Content = new ScrollView { Content = new VerticalStackLayout
        {
            Padding = 24, Spacing = 14,
            Children =
            {
                new Label { Text = "Votre PC, à portée de main", FontSize = 26, FontAttributes = FontAttributes.Bold },
                new Label { Text = "Activez le partage sur le PC, puis recopiez son adresse et son code. Même réseau Wi-Fi requis." },
                address, code,
                new Label { Text = "Réseau privé uniquement : cette version utilise HTTP, sans chiffrement.", FontSize = 12 },
                captureButton, appsButton, status,
                new Label { Text = "Écran principal", FontSize = 20, FontAttributes = FontAttributes.Bold }, screenshot,
                new Label { Text = "Applications ouvertes", FontSize = 20, FontAttributes = FontAttributes.Bold }, apps
            }
        }};
        captureButton.Clicked += async (_, _) => await RequestAsync(true);
        appsButton.Clicked += async (_, _) => await RequestAsync(false);
    }

    private async Task RequestAsync(bool capture)
    {
        if (!Uri.TryCreate(address.Text?.Trim(), UriKind.Absolute, out var baseUri)
            || (baseUri.Scheme != "http" && baseUri.Scheme != "https")
            || !string.IsNullOrEmpty(baseUri.UserInfo) || baseUri.AbsolutePath != "/"
            || !string.IsNullOrEmpty(baseUri.Query) || !string.IsNullOrEmpty(baseUri.Fragment))
        { status.Text = "Indiquez une adresse telle que http://192.168.1.10:5080"; return; }
        var token = code.Text?.Trim() ?? "";
        if (token.Length != 32 || !token.All(Uri.IsHexDigit))
        { status.Text = "Recopiez les 32 caractères du code affiché sur le PC."; return; }
        captureButton.IsEnabled = appsButton.IsEnabled = false;
        status.Text = "Demande en cours…";
        try
        {
            using var request = new HttpRequestMessage(HttpMethod.Get, new Uri(baseUri, capture ? "/api/screenshot" : "/api/apps"));
            request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
            using var response = await http.SendAsync(request);
            if (response.StatusCode == HttpStatusCode.Unauthorized)
            { status.Text = "Code incorrect. Vérifiez le code actuel sur le PC."; return; }
            response.EnsureSuccessStatusCode();
            if (capture)
            {
                var bytes = await response.Content.ReadAsByteArrayAsync();
                screenshot.Source = ImageSource.FromStream(() => new MemoryStream(bytes, writable: false));
            }
            else
            {
                var list = await response.Content.ReadFromJsonAsync<AppInfo[]>() ?? [];
                apps.Children.Clear();
                foreach (var app in list)
                    apps.Children.Add(new Label { Text = $"{app.Name} (PID {app.Id})\n{app.Title}" });
                if (list.Length == 0) apps.Children.Add(new Label { Text = "Aucune application avec fenêtre visible." });
            }
            status.Text = $"Reçu à {DateTime.Now:T}";
        }
        catch (TaskCanceledException) { status.Text = "Délai dépassé. Vérifiez le Wi-Fi, le pare-feu et le partage sur le PC."; }
        catch (Exception ex) when (ex is HttpRequestException or System.Text.Json.JsonException or InvalidOperationException)
        { status.Text = "Connexion impossible ou réponse invalide. Vérifiez l'adresse, le partage et le pare-feu du PC."; }
        finally { captureButton.IsEnabled = appsButton.IsEnabled = true; }
    }

    private sealed record AppInfo(int Id, string Name, string Title);
}
