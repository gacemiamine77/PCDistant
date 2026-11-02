namespace PCDistant.Client;

public static class MauiProgram
{
    public static MauiApp CreateMauiApp() => MauiApp.CreateBuilder().UseMauiApp<App>().Build();
}

public sealed class App : Application
{
    public App() { MainPage = new NavigationPage(new MainPage()); }
}
